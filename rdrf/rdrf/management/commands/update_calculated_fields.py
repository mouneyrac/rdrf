import json

import requests
from django.core.management.base import BaseCommand

from rdrf.models.definition.models import CommonDataElement, RegistryForm, Section
from registry.patients.models import Patient
import urllib.parse

from datetime import datetime


class Command(BaseCommand):
    help = 'Update calculated field values. It is mainly use to trigger periodic update.'

    def add_arguments(self, parser):
        parser.add_argument('--patient_id', action='append', type=int,
                            help='Only calculate the fields for a specific patient')
        parser.add_argument('--registry_id', action='append', type=int,
                            help='Only calculate the fields for a specific registry')
        parser.add_argument('--cde_id', action='append', type=int, help='Only calculate the fields for a specific CDE')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(options['patient_id']))
        self.stdout.write(self.style.SUCCESS('All fields have been successfully updated'))

        ##################### ALGO #########################################################

        print("")
        print("========================= BEGIN ===============================")
        print("")

        # retrieve all cde with a calculated field
        cdes = CommonDataElement.objects.exclude(calculation='')
        for cde in cdes:
            print(f"Code: {cde.code}")

        # Building the tree of form values so we can access them quickly.
        # for all registry
        # for all form
        # for all sections
        # if at least one cde is calculated
        # for all cde
        # save cde_values_dict {..., registry_id:{..., form_id:{..., section_id:{..., cde_id:cde}}}}
        forms = RegistryForm.objects.all()
        cde_values_dict = {}
        datacdes = {}
        print("")
        print("===== BUILDING THE CDE VALUES TREE FOR FORMS CONTAINING AT LEAST ONE CALCULATED CDE =====")
        print("")

        for form in forms:

            sections = Section.objects.filter(code__in=form.get_sections())

            if any(i.code in section.get_elements() for i in cdes for section in sections):

                for section in sections:

                    # print(f"section : {section} - elements: {section.get_elements()}")
                    for cde in section.get_elements():
                        # check if we already retrieved some values.
                        if cde_values_dict \
                                and form.registry.code in cde_values_dict \
                                and form.name in cde_values_dict[form.registry.code] \
                                and section.code in cde_values_dict[form.registry.code][form.name]:
                            existingvalues = cde_values_dict[form.registry.code][form.name][section.code]
                        else:
                            existingvalues = {}
                        # check if we already retrieved some sections.
                        if cde_values_dict \
                                and form.registry.code in cde_values_dict \
                                and form.name in cde_values_dict[form.registry.code]:
                            existingsections = cde_values_dict[form.registry.code][form.name]
                        else:
                            existingsections = {}
                        # check if we already retrieved some forms.
                        if cde_values_dict \
                                and form.registry.code in cde_values_dict:
                            existingforms = cde_values_dict[form.registry.code]
                        else:
                            existingforms = {}
                        # record cde objects so we don't retrieve twice the same cde object
                        if cde in datacdes.keys():
                            cdeobject = datacdes[cde]
                        else:
                            cdeobject = CommonDataElement.objects.get(code=cde)
                            datacdes[cde] = cdeobject
                        # add the cde to the dictionary
                        cde_values_dict = {**cde_values_dict,
                                           form.registry.code: {**existingforms,
                                                                form.name: {**existingsections,
                                                                            section.code: {**existingvalues,
                                                                                           cde: cdeobject}}}}

        print(f"{cde_values_dict}")

        print("")
        print(
            "=============================== CALL WS AND STORE NEW VALUES IN DB =========================================")
        print("")

        # for registry in cde_values_dict:
        #     print(registry)
        # patients = PatientManager.get_by_registry(registry)
        # print(patients)

        # all data cdes (so we know all about cde especially their datatype)

        # for all patient
        patients = Patient.objects.all()
        for patient in patients:
            # for all patient registry
            for registry in patient.rdrf_registry.all():
                # if registry is in the cde_values_dict
                if registry.code in cde_values_dict:
                    for form in cde_values_dict[registry.code]:
                        jscontextvar = {}

                        for section in cde_values_dict[registry.code][form]:

                            for cdecode in cde_values_dict[registry.code][form][section]:
                                try:
                                    cdevalue = patient.get_form_value(registry_code=registry.code,
                                                                      data_element_code=cdecode, form_name=form,
                                                                      section_code=section)
                                    # if cde is a date then display the JS format.
                                    # print(f"CDE TYPE: {cde_values_dict[registry.code][form][section][cdecode].datatype}")
                                    if cde_values_dict[registry.code][form][section][cdecode].datatype == 'date':
                                        cdevalue = datetime.strptime(cdevalue, '%Y-%m-%d').__format__("%d-%m-%Y")
                                        # print(f"DATE: {cdevalue}")
                                    jscontextvar[cdecode] = cdevalue
                                except KeyError:
                                    print(f"IGNORING EMPTY CDE VALUE {[c.id for c in patient.context_models]} | {registry.code} | {form} | {section} | {cdecode}")

                        # for each calculayed cdes in this form, do a WS call
                        for calculatedcde in cdes:
                            if calculatedcde.code in jscontextvar.keys():

                                print(f"{calculatedcde.code}")
                                print(f"CALCULATION: {calculatedcde.calculation}")
                                print(f"PATIENT: {patient}")
                                print(f"PATIENT DATE OF BIRTH: {patient.date_of_birth.__format__('%Y-%m-%d')}")
                                simple_patient = {'sex': patient.sex, 'date_of_birth': patient.date_of_birth.__format__("%Y-%m-%d")}
                                print(f"CONTEXT: {jscontextvar}")
                                mockcode = """
                                class Rdrf {
                                    log(msg) {
                                        console.log(msg);
                                    }
                                
                                    get(...anything) {
                                        console.log("A function is calling RDRF.get ADSAFE - ignoring...");
                                    }
                                }
                                
                                RDRF = new Rdrf();"""
                                context_js_code = f"{mockcode} patient = {json.dumps(simple_patient)}; context = {json.dumps(jscontextvar)}; {calculatedcde.calculation}"
                                headers = {'Content-Type': 'application/json'}

                                # jscode = {
                                #     "jscode": "const%20context%20%3D%20%7BmndCuttingFood%3A1%2C%0AmndCuttingFoodWithGastrodtomy%3A1%2C%0AmndSpeech%3A1%2C%0AmndSalivation%3A1%2C%0AmndSwallowing%3A1%2C%0AmndHandwriting%3A1%2C%0AmndDressingHygiene%3A1%2C%0AmndBed%3A1%2C%0AmndWalking%3A1%2C%0AmndClimbingStairs%3A1%2C%0AmndDyspnea%3A1%2C%0AmndOrthopnea%3A1%2C%0AmndRespiratoryInsufficiency%3A1%2C%0A%7D%3B%0A%0Afunction%20bad%28value%29%20%7B%0A%20%20%20return%20%20%28value%20%3D%3D%3D%20null%29%20%7C%7C%20%28%20value%20%3D%3D%3D%20undefined%29%20%7C%7C%20isNaN%28value%29%3B%0A%7D%0A%0Afunction%20getFloat%28x%29%20%7B%0A%20%20%20var%20y%20%3D%20parseFloat%28x%29%3B%0A%20%20%20if%20%28%21%20isNaN%28y%29%29%20%7B%0A%20%20%20%20%20%20%20return%20y%3B%0A%20%20%20%7D%0A%20%20%20return%20null%3B%0A%7D%0A%0Afunction%20getFilledOutScore%28x%2Cy%29%20%7B%0A%20%20%20var%20xval%20%3D%20getFloat%28x%29%3B%0A%20%20%20if%20%28xval%20%21%3D%3D%20null%29%20%7B%0A%20%20%20%20%20%20return%20xval%3B%0A%20%20%20%7D%0A%20%20%20return%20getFloat%28y%29%3B%0A%7D%0A%0Afunction%20getOptionE%28context%29%20%7B%0A%20var%20cutting%20%3D%20%20parseInt%28context.mndCuttingFood%2C%2010%29%3B%0A%20var%20gastrostomy%20%3D%20%20parseInt%28context.mndCuttingFoodWithGastrodtomy%2C%2010%29%3B%0A%20return%20getFilledOutScore%28cutting%2C%20gastrostomy%29%3B%0A%7D%0A%0Avar%20speech%3D%20parseInt%28context.mndSpeech%2C%2010%29%3B%0Avar%20salivation%20%3D%20parseInt%28context.mndSalivation%2C%2010%29%3B%0Avar%20swallowing%20%3D%20%20parseInt%28context.mndSwallowing%2C%2010%29%3B%0Avar%20handwriting%20%3D%20%20parseInt%28context.mndHandwriting%2C%2010%29%3B%0Avar%20hygiene%20%3D%20%20parseInt%28context.mndDressingHygiene%2C%2010%29%3B%0Avar%20bed%20%3D%20%20parseInt%28context.mndBed%2C%2010%29%3B%0Avar%20walking%20%3D%20%20parseInt%28context.mndWalking%2C%2010%29%3B%0Avar%20climbing%20%3D%20%20parseInt%28context.mndClimbingStairs%2C%2010%29%3B%0Avar%20dyspnea%20%3D%20%20parseInt%28context.mndDyspnea%2C%2010%29%3B%0Avar%20orthopnea%20%3D%20%20parseInt%28context.mndOrthopnea%2C%2010%29%3B%0Avar%20respiratory%20%3D%20parseInt%28context.mndRespiratoryInsufficiency%2C%2010%29%3B%0A%0Avar%20cutting_filled%20%3D%20getOptionE%28context%29%3B%0A%0Avar%20total%20%3D%20%28speech%20%2B%20salivation%20%2B%20swallowing%20%2B%20handwriting%20%2B%20cutting_filled%20%2B%20hygiene%20%2B%20bed%20%2B%20walking%20%2B%20climbing%20%2B%20dyspnea%20%2B%20orthopnea%20%2B%20respiratory%29%3B%0A%0Acontext.result%20%3D%20total%3B"}
                                jscode = {"jscode": urllib.parse.quote(context_js_code)}
                                # print(jscode)

                                resp = requests.post(url='http://node_js_evaluator:3131/eval', headers=headers,
                                                     json=jscode)
                                print('Result: {}'.format(resp.json()))
                                print(f"----------------------- END CALCULATION --------------------------")

                        # store the new form value in the ClinicalData model

        print("")
        print("========================== END ===============================")
        print("")

        # Run some test
        # set data
        # Code: CDE00024
        #   CDE00013 LDLCholesterolAdjTreatment CDE00004 CDE00003 FHFamHistTendonXanthoma FHFamHistArcusCornealis CDEfhDutchLipidClinicNetwork DateOfAssessment
        #   CDEIndexOrRelative

        # Code: CDEBMI
        #   CDEHeight CDEWeight

        # Code: CDEfhDutchLipidClinicNetwork
        #   CDE00013 LDLCholesterolAdjTreatment DateOfAssessment CDEIndexOrRelative CDE00004 CDE00003 FHFamilyHistoryChild FHFamHistTendonXanthoma FHFamHistArcusCornealis
        #   CDE00011 FHPersHistCerebralVD CDE00001 CDE00002

        # Code: FHDeathAge
        #   FHDeathDate

        # Code: LDLCholesterolAdjTreatment
        #   CDE00019 PlasmaLipidTreatment

        # Code: fhAgeAtAssessment
        #   DateOfAssessment

        # Code: fhAgeAtConsent
        #   FHconsentDate
