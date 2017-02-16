# -*- encoding: utf-8 -*-
import logging
import os
import yaml
from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase, RequestFactory

from .exporter import Exporter, ExportType
from .importer import Importer, ImportState
from .models import Registry, RegistryForm, Section
from .models import CDEPermittedValueGroup, CDEPermittedValue
from .models import CommonDataElement
from .models import Modjgo
from .form_view import FormView
from registry.patients.models import Patient
from registry.patients.models import State, PatientAddress, AddressType
from registry.groups.models import WorkingGroup, CustomUser
from .utils import de_camelcase, check_calculation, TimeStripper
from copy import deepcopy

logger = logging.getLogger(__name__)

def mock_messages():
    """
    This switches off messaging, which requires request middleware
    which doesn't exist in RequestFactory requests.
    """
    def mock_add_message(request, level, msg, *args, **kwargs):
        logger.info("Django %s Message: %s" % (level, msg))
    def mock_error(request, msg, *args, **kwargs):
        logger.info("Django Error Message: %s" % msg)
    messages.add_message = mock_add_message
    messages.error = mock_error
mock_messages()


class SectionFiller(object):

    def __init__(self, form_filler, section):
        self.__dict__["form_filler"] = form_filler
        self.__dict__["section"] = section

    def __setattr__(self, key, value):
        if key in self.section.get_elements():
            self.form_filler.add_data(self.section, key, value)


class FormFiller(object):

    def __init__(self, registry_form):
        self.form = registry_form
        self.section_codes = self.form.get_sections()
        self.data = {}

    def add_data(self, section, cde_code, value):
        key = settings.FORM_SECTION_DELIMITER.join([self.form.name, section.code, cde_code])
        self.data.update({key: value})

    def __getattr__(self, item):
        if item in self.section_codes:
            section = Section.objects.get(code=item)
            section_filler = SectionFiller(self, section)
            return section_filler


class RDRFTestCase(TestCase):
    fixtures = ['testing_auth', 'testing_users', 'testing_rdrf']


class TestFormPermissions(RDRFTestCase):

    def test_form_without_groups_restriction_is_open(self):
        from registry.groups.models import CustomUser
        fh = Registry.objects.get(code='fh')

        for form in fh.forms:
            assert form.open, "%s has no group restriction so should be open but is not" % form.name
            for user in CustomUser.objects.all():
                user.registry.add(fh)
                user.save()
                assert user.can_view(form)

    def test_user_in_wrong_group_cant_view_form(self):
        from registry.groups.models import CustomUser
        from django.contrib.auth.models import Group
        fh = Registry.objects.get(code='fh')
        genetic_user = CustomUser.objects.get(username='genetic')
        genetic_group, created = Group.objects.get_or_create(name="Genetic Staff")
        if created:
            genetic_group.save()

        clinical_group, created = Group.objects.get_or_create(name="Clinical Staff")
        if created:
            clinical_group.save()
        f = fh.forms[0]
        f.groups_allowed = [clinical_group]
        f.save()
        assert not genetic_user.can_view(f), "A form set to be viewed "


class ExporterTestCase(RDRFTestCase):

    def _get_cde_codes_from_registry_export_data(self, data):
        cde_codes = set([])
        for form_map in data["forms"]:
            for section_map in form_map["sections"]:
                for cde_code in section_map["elements"]:
                    cde_codes.add(cde_code)
        return cde_codes

    def _report_cde_diff(self, cde_set, cdeform_set):
        in_cdes_not_forms = cde_set - cdeform_set
        in_forms_not_cdes = cdeform_set - cde_set
        a = "cdes in cde list but not in registry: %s" % in_cdes_not_forms
        b = "cdes in forms but not in cde list: %s" % in_forms_not_cdes
        return "%s\n%s" % (a, b)

    def test_export_registry(self):

        def test_key(key, data):
            assert key in data, "%s not in yaml export" % key

        def test_keys(keys, data):
            for key in keys:
                test_key(key, data)

        self.registry = Registry.objects.get(code='fh')
        self.exporter = Exporter(self.registry)
        yaml_data, errors = self.exporter.export_yaml()
        assert isinstance(errors, list), "Expected errors list in exporter export_yaml"
        assert len(errors) == 0, "Expected zero errors instead got:%s" % errors
        assert isinstance(yaml_data, str), "Expected yaml_data is  string:%s" % type(yaml_data)
        with open("/tmp/test.yaml", "w") as f:
            f.write(yaml_data)

        with open("/tmp/test.yaml") as f:
            data = yaml.load(f)

        test_key('EXPORT_TYPE', data)
        test_key('RDRF_VERSION', data)
        assert data["EXPORT_TYPE"] == ExportType.REGISTRY_PLUS_CDES
        assert 'cdes' in data, "Registry export should have cdes key"
        assert 'pvgs' in data, "Registry export should have groups key"
        assert data['code'] == 'fh', "Reg code fh not in export"
        test_key('forms', data)
        for form_map in data['forms']:
            test_keys(['is_questionnaire', 'name', 'sections'], form_map)
            for section_map in form_map['sections']:
                test_keys(['code',
                           'display_name',
                           'elements',
                           'allow_multiple',
                           'extra'],
                          section_map)

        from rdrf.models import CommonDataElement
        dummy_cde = CommonDataElement.objects.create()
        cde_fields = list(model_to_dict(dummy_cde).keys())
        for cde_map in data['cdes']:
            assert isinstance(
                cde_map, dict), "Expected cdes list should contain cde dictionaries: actual %s" % cde_map
            for cde_field in cde_fields:
                assert cde_field in cde_map, "Expected export of cde to contain field %s - it doesn't" % cde_field

        for pvg_map in data["pvgs"]:
            assert "code" in pvg_map, "Expected group has code key: %s" % pvg_map
            assert "values" in pvg_map, "Expected group has values key: %s" % pvg_map
            for value_map in pvg_map["values"]:
                assert "code" in value_map, "Expected value map to have code key %s" % value_map
                assert "value" in value_map, "Expected value map to have value key %s" % value_map
                assert "desc" in value_map, "Expected value map to have desc key %s" % value_map

        # consistency check
        set_of_cde_codes_in_cdes = set([cde_map["code"] for cde_map in data["cdes"]])
        set__of_cdes_in_forms = self._get_cde_codes_from_registry_export_data(data)
        generic_cdes = set(self.registry.generic_cdes)

        assert set__of_cdes_in_forms == (
            set_of_cde_codes_in_cdes - generic_cdes), "Consistency check failed:\n%s" % self._report_cde_diff(set_of_cde_codes_in_cdes, set__of_cdes_in_forms)

        # consistency of values in groups - whats exported is whats there

        for pvg_map in data["pvgs"]:
            values_in_export = set([])
            for value_map in pvg_map["values"]:
                values_in_export.add(value_map["code"])

            values_in_db = self._get_values_for_group(pvg_map["code"])
            msg = "%s:export %s\ndb: %s" % (pvg_map["code"], values_in_export, values_in_db)
            assert values_in_export == values_in_db, "Values in export for group %s don't match what's in db: %s" % msg

    def _get_values_for_group(self, group_code):
        values = set([])
        group = CDEPermittedValueGroup.objects.get(code=group_code)
        for value in CDEPermittedValue.objects.filter(pv_group=group):
            values.add(value.code)
        return values


class ImporterTestCase(TestCase):

    def _get_yaml_file(self):
        return os.path.join(os.path.dirname(__file__), 'fixtures', 'exported_fh_registry.yaml')

    def test_importer(self):
        importer = Importer()
        yaml_file = self._get_yaml_file()

        importer.load_yaml(yaml_file)
        importer.create_registry()
        assert importer.state == ImportState.SOUND


class FormTestCase(RDRFTestCase):

    def setUp(self):
        super(FormTestCase, self).setUp()
        self.registry = Registry.objects.get(code='fh')
        self.user = CustomUser.objects.get(username="curator")
        self.user.registry = [self.registry]
        self.user.save()

        self.state, created = State.objects.get_or_create(
            short_name="WA", name="Western Australia")

        self.state.save()
        self.create_sections()
        self.working_group, created = WorkingGroup.objects.get_or_create(name="WA")
        self.working_group.save()
        self.create_forms()

        self.patient = self.create_patient()

        self.address_type, created = AddressType.objects.get_or_create(pk=1)

        self.patient_address, created = PatientAddress.objects.get_or_create(
            address='1 Line St', address_type=self.address_type, suburb='Neverland', state=self.state.short_name, postcode='1111', patient=self.patient)
        self.patient_address.save()

        self.request_factory = RequestFactory()

    def create_patient(self):
        from rdrf.contexts_api import RDRFContextManager

        p = Patient()
        p.consent = True
        p.name = "Harry"
        p.date_of_birth = datetime(1978, 6, 15)
        p.working_group = self.working_group
        p.save()
        p.rdrf_registry = [self.registry]

        context_manager = RDRFContextManager(self.registry)
        self.default_context = context_manager.get_or_create_default_context(p, new_patient=True)

        return p

    def create_section(self, code, display_name, elements, allow_multiple=False, extra=1):
        section, created = Section.objects.get_or_create(code=code)
        section.display_name = display_name
        section.elements = ",".join(elements)
        section.allow_multiple = allow_multiple
        section.extra = extra
        section.save()
        return section

    def create_form(self, name, sections, is_questionnnaire=False):
        sections = ",".join([section.code for section in sections])
        form, created = RegistryForm.objects.get_or_create(name=name, registry=self.registry,
                                                           defaults={'sections': sections})
        if not created:
            form.sections = sections
        form.name = name
        form.registry = self.registry
        form.is_questionnaire = is_questionnnaire
        form.save()
        # self.working_group
        return form

    def create_forms(self):
        self.simple_form = self.create_form("simple", [self.sectionA, self.sectionB])
        self.multi_form = self.create_form("multi", [self.sectionC])
        # TODO file forms, questionnaire forms

    def _create_request(self, form_obj, form_data):
        # return a dictionary representing what is sent from filled in form
        # form data looks like:
        # { "
        url = "/%s/forms/%s/%s" % (form_obj.registry.code, form_obj.pk, self.patient.pk)

        request = self.request_factory.post(url, form_data)
        request.user = get_user_model().objects.get(username="curator")
        return request

    def create_sections(self):
        # "simple" sections ( no files or multi-allowed sections
        self.sectionA = self.create_section(
            "sectionA", "Simple Section A", ["CDEName", "CDEAge"])
        self.sectionB = self.create_section(
            "sectionB", "Simple Section B", ["CDEHeight", "CDEWeight"])
        # A multi allowed section with no file cdes
        self.sectionC = self.create_section(
            "sectionC", "MultiSection No Files Section C", ["CDEName", "CDEAge"], True)
        # A multi allowed section with a file CDE
        # self.sectionD = self.create_section("sectionD", "MultiSection With Files D", ["CDEName", ""])

    def _create_form_key(self, form, section, cde_code):
        return settings.FORM_SECTION_DELIMITER.join([form.name, section.code, cde_code])

    def test_patient_archiving(self):
        from registry.patients.models import Patient
        
        patient_model = self.create_patient()
        self.assertTrue(patient_model.active)
        
        my_id = patient_model.pk

        patient_model.delete()
        self.assertEqual(patient_model.active, False)

        # should not be findable
        with self.assertRaises(Patient.DoesNotExist):
            dummy = Patient.objects.get(id=my_id)

        # test really_all object manager method on Patients
        self.assertEqual(my_id, Patient.objects.really_all().get(id=my_id).id)

        # test hard delete

        patient_model._hard_delete()

        with self.assertRaises(Patient.DoesNotExist):
            dummy = Patient.objects.get(id=my_id)

        with self.assertRaises(Patient.DoesNotExist):
            dummy = Patient.objects.really_all().get(id=my_id)


        # test can archive prop on CustomUser
        # by default genetic user can't delete as they don't have patient delete permission

        genetic_user = CustomUser.objects.get(username='genetic')
        self.assertFalse(genetic_user.can_archive)

        # admin can by default
        admin_user = CustomUser.objects.get(username='admin')
        self.assertTrue(admin_user.can_archive)

        # clinical can't either
        clinical_user = CustomUser.objects.get(username='clinical')
        self.assertFalse(clinical_user.can_archive)

        
        
        
        

    def test_simple_form(self):

        def form_value(form_name, section_code, cde_code, mongo_record):
            for form in mongo_record["forms"]:
                if form["name"] == form_name:
                    for section in form["sections"]:
                        if section["code"] == section_code:
                            for cde in section["cdes"]:
                                if cde["code"] == cde_code:
                                    return cde["value"]

        ff = FormFiller(self.simple_form)
        ff.sectionA.CDEName = "Fred"
        ff.sectionA.CDEAge = 20
        ff.sectionB.CDEHeight = 1.73
        ff.sectionB.CDEWeight = 88.23

        form_data = ff.data
        print(str(form_data))
        request = self._create_request(self.simple_form, form_data)
        view = FormView()
        view.request = request
        view.post(request, self.registry.code, self.simple_form.pk, self.patient.pk, self.default_context.pk)

        collection = Modjgo.objects.collection(self.registry.code, "cdes")
        context_id = self.patient.default_context(self.registry).id
        mongo_record = collection.find(self.patient, context_id).data().first()

        print("*** MONGO RECORD = %s ***" % mongo_record)

        assert "forms" in mongo_record, "Mongo record should have a forms key"
        assert isinstance(mongo_record["forms"], list)
        assert len(mongo_record["forms"]) == 1, "Expected one form"

        the_form = mongo_record['forms'][0]
        assert isinstance(the_form, dict), "form data should be a dictionary"
        assert "sections" in the_form, "A form should have a sections key"
        assert isinstance(the_form["sections"], list), "Sections should be in a list"
        # we've only written data for 2 sections
        assert len(the_form["sections"]) == 2, "expected 2 sections got %s" % len(the_form["sections"])

        for section_dict in the_form["sections"]:
            assert isinstance(section_dict, dict), "sections should be dictioanaries"
            assert "cdes" in section_dict, "sections should have a cdes key"
            assert isinstance(section_dict["cdes"], list), "sections cdes key should be a list"
            for cde in section_dict["cdes"]:
                assert isinstance(cde, dict), "cde should be a dict"
                assert "code" in cde, "cde dictionary should have a code key"
                assert "value" in cde, "cde dictionary should have a value key"

        assert form_value(self.simple_form.name, self.sectionA.code, "CDEName", mongo_record) == "Fred"
        assert form_value(self.simple_form.name, self.sectionA.code, "CDEAge", mongo_record) == 20
        assert form_value(self.simple_form.name, self.sectionB.code, "CDEHeight", mongo_record) == 1.73
        assert form_value(self.simple_form.name, self.sectionB.code, "CDEWeight", mongo_record) == 88.23


class LongitudinalTestCase(FormTestCase):

    def test_simple_form(self):
        super(LongitudinalTestCase, self).test_simple_form()
        # should have one snapshot
        qs = Modjgo.objects.collection(self.registry.code, "history")
        snapshots = qs.find(self.patient, record_type="snapshot").data()
        self.assertGreater(len(snapshots), 0,
                           "History should be filled in on save")
        for snapshot in snapshots:
            self.assertIn("record", snapshot,
                          "Each snapshot should have a record field")
            self.assertIn("timestamp", snapshot,
                          "Each snapshot should have a timestamp field")
            self.assertIn("forms", snapshot["record"],
                          "Each  snapshot should record dict contain a forms field")


class DeCamelcaseTestCase(TestCase):

    _EXPECTED_VALUE = "Your Condition"

    def test_decamelcase_first_lower(self):
        test_value = "yourCondition"
        self.assertEqual(de_camelcase(test_value), self._EXPECTED_VALUE)

    def test_decamelcase_first_upper(self):
        test_value = "YourCondition"
        self.assertEqual(de_camelcase(test_value), self._EXPECTED_VALUE)


class JavascriptCheckTestCase(TestCase):

    def test_empty_script(self):
        err = check_calculation("")
        self.assertEqual(err, "")

    def test_simple(self):
        err = check_calculation("var test = 42;")
        self.assertEqual(err, "")

    def test_context_result(self):
        err = check_calculation("context.result = 42;")
        self.assertEqual(err, "")

    def test_patient_context(self):
        err = check_calculation("context.result = patient.age / 2 + 7;")
        self.assertEqual(err, "")

    def test_adsafe_this(self):
        err = check_calculation("this.test = true;")
        self.assertTrue(err)

    def test_lint_dodgy(self):
        err = check_calculation("// </script>")
        self.assertTrue(err)

    def test_adsafe_subscript(self):
        err = check_calculation("""
           var i = 42;
           context[i] = "hello";
        """)
        self.assertTrue(err)

    def test_date(self):
        err = check_calculation("context.result = new Date();")
        self.assertEqual(err, "")

    def test_nonascii(self):
        err = check_calculation("context.result = '💩';")
        self.assertEqual(err, "")


class FakeModjgo(object):
            def __init__(self, pk, data):
                self.pk = pk
                self.data = data
            def save(self):
                print("Fake Modjgo save called")


class TimeStripperTestCase(TestCase):
    def setUp(self):
        super(TimeStripperTestCase, self).setUp()

        
        self.data_with_date_cdes = {'django_model': 'Patient',
                                    'ClinicalData_timestamp': '2017-02-14T10:23:10.601182',
                                    'context_id': 4,
                                    'django_id': 3,
                                    'forms': [{'name': 'ClinicalData',
                                               'sections': [{'code': 'fhDateSection', 'allow_multiple': False,
                                                             'cdes': [{'value': 'fh_is_index', 'code': 'CDEIndexOrRelative'},
                                                                      {'value': '1972-06-15T00:00:00.00', 'code': 'DateOfAssessment'},
                                                                      {'value': '2015-01-05T10:23:10.601182', 'code': 'FHconsentDate'}]},
                                                            {'code': 'SEC0007', 'allow_multiple': False,
                                                             'cdes': [{'value': '', 'code': 'CDE00024'},
                                                                      {'value': '', 'code': 'CDEfhDutchLipidClinicNetwork'}]}]}]}

        self.copy_of_initial_data = deepcopy(self.data_with_date_cdes)
        
        
        self.data_without_date_cdes =  {'django_model': 'Patient',
                                    'ClinicalData_timestamp': '2017-02-14T10:23:10.601182',
                                    'context_id': 40,
                                    'django_id': 300,
                                    'forms': [{'name': 'ClinicalData',
                                               'sections': [{'code': 'fhDateSection', 'allow_multiple': False,
                                                             'cdes': [{'value': 'fh_is_index', 'code': 'CDEIndexOrRelative'}]},
                                                            {'code': 'SEC0007', 'allow_multiple': False,
                                                             'cdes': [{'value': '', 'code': 'CDE00024'},
                                                                      {'value': '', 'code': 'CDEfhDutchLipidClinicNetwork'}]}]}]}

        

        self.m1 = FakeModjgo(1, self.data_with_date_cdes)
        self.m2 = FakeModjgo(2, self.data_without_date_cdes)

        self.ts = TimeStripper([self.m1, self.m2])
        self.ts.test_mode = True
        self.ts.date_cde_codes = ['DateOfAssessment', 'FHconsentDate']
        

    def test_timestripper(self):
        a = deepcopy(self.data_with_date_cdes)

        expected_date_of_assessment = "1972-06-15"
        expected_fh_consent_date = "2015-01-05"
        expected = [expected_date_of_assessment, expected_fh_consent_date]
        ClinicalData_timestamp_before = self.data_with_date_cdes["ClinicalData_timestamp"]
        fh_index_before  = self.data_with_date_cdes["forms"][0]["sections"][0]["cdes"][0]["value"]
        
        
        self.ts.forward()
        ClinicalData_timestamp_after = self.data_with_date_cdes["ClinicalData_timestamp"]
        fh_index_after  = self.data_with_date_cdes["forms"][0]["sections"][0]["cdes"][0]["value"]


        self.assertTrue(self.ts.converted_date_cdes == expected,
                        "Expected %s Actual %s" % (expected, self.ts.converted_date_cdes))

        value1 = self.data_with_date_cdes["forms"][0]["sections"][0]["cdes"][1]["value"]
        self.assertTrue(value1 == expected_date_of_assessment, "DateOfAssessment value not modified by TimeStripper")
        value2 = self.data_with_date_cdes["forms"][0]["sections"][0]["cdes"][2]["value"]
        self.assertTrue(value2 == expected_fh_consent_date, "FHConsentdate value not modified by TimeStripper")

        self.assertTrue(ClinicalData_timestamp_after == ClinicalData_timestamp_before, "Timestamps which are not date cdes should not be affected by TimeStripper")
        self.assertTrue(fh_index_before == fh_index_after, "Non date cdes should not be affected by TimeStripper")



    def test_update_of_multisections(self):
        # multisection with 2 items , one cde Surgery , another SurgeryDate
        cde_dict1 = {"code": "Surgery", "value": "Appendix Removed"}
        cde_dict2 = {"code": "SurgeryDate", "value": "2017-02-14T00:00:00"}
        cde_dict3 = {"code": "Surgery", "value": "Stomach Ulcer"}
        cde_dict4 = {"code": "SurgeryDate", "value": "2018-03-26T00:00:00"}
        # assume last item ok
        cde_dict5 = {"code": "Surgery", "value": "Heart Surgery"}
        cde_dict6 = {"code": "SurgeryDate", "value": "2011-11-05"}
        
        item1 = [cde_dict1, cde_dict2]
        item2 = [cde_dict3, cde_dict4]
        item3 = [cde_dict5, cde_dict6]

        multisection = {"allow_multiple": True,
                        "cdes" : [item1, item2, item3]}
        
        
        data_with_multisections = {"forms": [ {"form": "testing",
                                               "sections": [multisection]}]}
        
        copy_before_op = deepcopy(data_with_multisections)
        m = FakeModjgo(23, data_with_multisections)

        ts = TimeStripper([m])
        ts.test_mode = True
        ts.date_cde_codes = ['SurgeryDate']

        ts.forward()

        self.assertTrue(ts.converted_date_cdes == ["2017-02-14", "2018-03-26"],
                        "Multisection timestrip failed: actual = %s" % ts.converted_date_cdes)


        expected_value1 = "2017-02-14"
        actual_value1 = m.data["forms"][0]["sections"][0]["cdes"][0][1]["value"]
        self.assertEqual(expected_value1, actual_value1,
                         "Update of multisection failed for first item: actual = %s" % actual_value1)

        expected_value2 = "2018-03-26"
        actual_value2 = m.data["forms"][0]["sections"][0]["cdes"][1][1]["value"]
        self.assertEqual(expected_value2, actual_value2,
                         "Update of multisection failed for second item: actual = %s" % actual_value2)
        
        expected_value3 = "2011-11-05" #n shouldn't have changed
        actual_value3 = m.data["forms"][0]["sections"][0]["cdes"][2][1]["value"]
        self.assertEqual(expected_value2, actual_value2,
                         "Update of multisection failed for third item: actual = %s" % actual_value3)


    def test_history_munging(self):
        from rdrf.utils import HistoryTimeStripper
        history_modjgo_data = { "django_id": 1,
                 "record": {
                "django_id": 1,
                      "timestamp": "2017-02-13T12:28:49.355839",
                      "forms": [
                        {
                          "sections": [
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "fh_is_index",
                                  "code": "CDEIndexOrRelative"
                                },
                                {
                                  "value": "2017-02-15",
                                  "code": "DateOfAssessment"
                                },
                                {
                                  "value": "2017-02-14T00:00:00.000",
                                  "code": "FHconsentDate"
                                }
                              ],
                              "code": "fhDateSection"
                            },
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "",
                                  "code": "CDE00024"
                                },
                                {
                                  "value": "",
                                  "code": "CDEfhDutchLipidClinicNetwork"
                                }
                              ],
                              "code": "SEC0007"
                            },
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "fh2_y",
                                  "code": "CDE00004"
                                },
                                {
                                  "value": "fh2_n",
                                  "code": "FHFamHistTendonXanthoma"
                                },
                                {
                                  "value": "fh2_n",
                                  "code": "FHFamHistArcusCornealis"
                                },
                                {
                                  "value": "fh2_y",
                                  "code": "CDE00003"
                                },
                                {
                                  "value": "y_childunder18",
                                  "code": "FHFamilyHistoryChild"
                                }
                              ],
                              "code": "SEC0002"
                            },
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "",
                                  "code": "FHSupravalvularDisease"
                                },
                                {
                                  "value": None,
                                  "code": "FHAgeAtMI"
                                },
                                {
                                  "value": None,
                                  "code": "FHAgeAtCV"
                                },
                                {
                                  "value": "",
                                  "code": "FHPremNonCoronary"
                                },
                                {
                                  "value": "",
                                  "code": "FHAorticValveDisease"
                                },
                                {
                                  "value": "fh2_n",
                                  "code": "FHPersHistCerebralVD"
                                },
                                {
                                  "value": "fhpremcvd_unknown",
                                  "code": "CDE00011"
                                },
                                {
                                  "value": "",
                                  "code": "FHCoronaryRevasc"
                                },
                                {
                                  "value": "",
                                  "code": "FHMyocardialInfarction"
                                }
                              ],
                              "code": "SEC0004"
                            },
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "u_",
                                  "code": "CDE00002"
                                },
                                {
                                  "value": "",
                                  "code": "FHXanthelasma"
                                },
                                {
                                  "value": "y",
                                  "code": "CDE00001"
                                }
                              ],
                              "code": "SEC0001"
                            },
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "",
                                  "code": "PlasmaLipidTreatment"
                                },
                                {
                                  "value": None,
                                  "code": "CDE00019"
                                },
                                {
                                  "value": "NaN",
                                  "code": "LDLCholesterolAdjTreatment"
                                },
                                {
                                  "value": None,
                                  "code": "CDE00013"
                                }
                              ],
                              "code": "FHLDLforFHScore"
                            },
                            {
                              "allow_multiple": True,
                              "cdes": [
                                [
                                  {
                                    "value": None,
                                    "code": "CDE00014"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHLipidProfileUntreatedDate"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHAlbum"
                                  },
                                  {
                                    "value": None,
                                    "code": "CDE00012"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHCK"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHA1"
                                  },
                                  {
                                    "value": "",
                                    "code": "PlasmaLipidTreatmentNone"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHAST"
                                  },
                                  {
                                    "value": None,
                                    "code": "CDE00015"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHApoB"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHALT"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHLLDLconc"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHCreatinine"
                                  },
                                  {
                                    "value": "",
                                    "code": "FHCompliance"
                                  },
                                  {
                                    "value": "",
                                    "code": "CDEfhOtherIntolerantDrug"
                                  },
                                  {
                                    "value": None,
                                    "code": "CDE00016"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHCRP"
                                  }
                                ]
                              ],
                              "code": "SEC0005"
                            },
                            {
                              "allow_multiple": False,
                              "cdes": [
                                {
                                  "value": "NaN",
                                  "code": "CDEBMI"
                                },
                                {
                                  "value": "",
                                  "code": "FHHypertriglycerd"
                                },
                                {
                                  "value": None,
                                  "code": "HbA1c"
                                },
                                {
                                  "value": "",
                                  "code": "FHHypothyroidism"
                                },
                                {
                                  "value": None,
                                  "code": "CDE00009"
                                },
                                {
                                  "value": None,
                                  "code": "FHHeartRate"
                                },
                                {
                                  "value": None,
                                  "code": "CDE00010"
                                },
                                {
                                  "value": None,
                                  "code": "FHWaistCirc"
                                },
                                {
                                  "value": "",
                                  "code": "FHObesity"
                                },
                                {
                                  "value": None,
                                  "code": "CDE00008"
                                },
                                {
                                  "value": None,
                                  "code": "CDEWeight"
                                },
                                {
                                  "value": None,
                                  "code": "FHPackYears"
                                },
                                {
                                  "value": None,
                                  "code": "CDEHeight"
                                },
                                {
                                  "value": "",
                                  "code": "CDE00007"
                                },
                                {
                                  "value": "",
                                  "code": "FHAlcohol"
                                },
                                {
                                  "value": "",
                                  "code": "CDE00005"
                                },
                                {
                                  "value": "",
                                  "code": "CDE00006"
                                },
                                {
                                  "value": "",
                                  "code": "FHCVDOther"
                                },
                                {
                                  "value": None,
                                  "code": "FHeGFR"
                                },
                                {
                                  "value": "",
                                  "code": "ChronicKidneyDisease"
                                },
                                {
                                  "value": "",
                                  "code": "FHHepaticSteatosis"
                                },
                                {
                                  "value": None,
                                  "code": "FHTSH"
                                }
                              ],
                              "code": "SEC0003"
                            },
                            {
                              "allow_multiple": True,
                              "cdes": [
                                [
                                  {
                                    "value": "",
                                    "code": "FHTrialStatus"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHTrialSTartDate"
                                  },
                                  {
                                    "value": "",
                                    "code": "FHClinicalTrialName"
                                  },
                                  {
                                    "value": None,
                                    "code": "FHTrialLength"
                                  }
                                ]
                              ],
                              "code": "FHClinicalTrials"
                            }
                          ],
                          "name": "ClinicalData"
                        }
                      ],
                      "context_id": 1,
                      "ClinicalData_timestamp": "2017-02-13T12:28:49.355839",
                      "django_model": "Patient"
                    },
                    "record_type": "snapshot",
                    "timestamp": "2017-02-13 12:28:49.665333",
                    "registry_code": "fh",
                    "context_id": 1,
                    "django_model": "Patient"
                  }

        expected_dates = ['2017-02-14']
        history_record = FakeModjgo(73, history_modjgo_data)
        ts = HistoryTimeStripper([history_record])
        ts.test_mode = True
        ts.date_cde_codes = ['FHconsentDate']
        ts.forward()
        

        
        self.assertTrue(ts.converted_date_cdes == expected_dates,
                        "Expected: %s, Actual: %s" % (expected_dates,
                                                      ts.converted_date_cdes))

