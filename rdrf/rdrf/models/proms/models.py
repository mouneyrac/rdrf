import logging
import requests

from django.db import models
from django.urls import reverse

from rdrf.models.definition.models import Registry
from rdrf.models.definition.models import CommonDataElement
from rdrf.services.io.notifications.notifications import Notifier
from rdrf.services.io.notifications.notifications import NotificationError
from registry.patients.models import Patient
from rdrf.helpers.utils import generate_token

from rest_framework import status

logger = logging.getLogger(__name__)


class PromsRequestError(Exception):
    pass


class PromsEmailError(Exception):
    pass


class Survey(models.Model):
    registry = models.ForeignKey(Registry, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    display_name = models.CharField(max_length=80, blank=True, null=True)
    is_followup = models.BooleanField(default=False)

    @property
    def client_rep(self):
        return [sq.client_rep for sq in self.survey_questions.all().order_by('position')]

    def __str__(self):
        return "%s Survey: %s" % (self.registry.code, self.name)

    def clean(self):
        for question in self.survey_questions.all():
            logger.debug("checking survey q %s" % question.cde.code)
            if question.cde.datatype != "range":
                logger.debug("%s not a range" % question.cde.code)
                # raise ValidationError("Survey questions must be ranges")


class Precondition(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    cde = models.ForeignKey(CommonDataElement, on_delete=models.CASCADE)
    value = models.CharField(max_length=80)

    def __str__(self):
        return "if <<%s>> = %s" % (self.cde,
                                   self.value)


class SurveyQuestion(models.Model):
    position = models.IntegerField(null=True, blank=True)
    survey = models.ForeignKey(Survey, related_name='survey_questions', on_delete=models.CASCADE)
    cde = models.ForeignKey(CommonDataElement, on_delete=models.CASCADE)
    precondition = models.ForeignKey(Precondition,
                                     blank=True,
                                     null=True,
                                     on_delete=models.SET_NULL)
    instruction = models.TextField(blank=True, null=True)
    copyright_text = models.TextField(blank=True, null=True)
    source = models.TextField(blank=True, null=True)

    @property
    def name(self):
        return self.cde.name

    def _clean_instructions(self, instructions):
        return instructions.replace("\n", " ").replace("\r", " ")

    @property
    def client_rep(self):
        # client side representation
        if not self.precondition:
            return {"tag": "cde",
                    "cde": self.cde.code,
                    "datatype": self.cde.datatype,
                    "instructions": self._clean_instructions(self.cde.instructions),
                    "title": self.cde.name,
                    "survey_question_instruction": self.instruction,
                    "copyright_text": self.copyright_text,
                    "source": self.source,
                    "spec": self._get_cde_specification()}

        else:
            return {"tag": "cond",
                    "cde": self.cde.code,
                    "instructions": self._clean_instructions(self.cde.instructions),
                    "title": self.cde.name,
                    "spec": self._get_cde_specification(),
                    "survey_question_instruction": self.instruction,
                    "copyright_text": self.copyright_text,
                    "source": self.source,
                    "cond": {"op": "=",
                             "cde": self.precondition.cde.code,
                             "value": self.precondition.value
                             }
                    }

    def _get_options(self):
        if self.cde.datatype == 'range':
            return self.cde.pv_group.options
        else:
            return []

    def _get_cde_specification(self):
        if self.cde.datatype == 'range':
            return {
                "tag": "range",
                "options": self._get_options()
            }
        elif self.cde.datatype == 'integer':
            return {
                "tag": "integer",
                "max": int(self.cde.max_value),
                "min": int(self.cde.min_value)
            }

    @property
    def expression(self):
        if not self.precondition:
            return self.cde.name + " always"
        else:
            return self.cde.name + "  if " + self.precondition.cde.name + " = " + self.precondition.value


class SurveyStates:
    REQUESTED = "requested"
    STARTED = "started"
    COMPLETED = "completed"


class SurveyRequestStates:
    CREATED = "created"
    REQUESTED = "requested"
    RECEIVED = "received"
    ERROR = "error"


class CommunicationTypes:
    QRCODE = "qrcode"
    EMAIL = "email"


class SurveyAssignment(models.Model):
    """
    This gets created on the proms system
    """
    SURVEY_STATES = (
        (SurveyStates.REQUESTED, "Requested"),
        (SurveyStates.STARTED, "Started"),
        (SurveyStates.COMPLETED, "Completed"))
    registry = models.ForeignKey(Registry, on_delete=models.CASCADE)
    survey_name = models.CharField(max_length=80)
    patient_token = models.CharField(max_length=80, unique=True)
    state = models.CharField(max_length=20, choices=SURVEY_STATES)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    response = models.TextField(blank=True, null=True)

    @property
    def survey(self):
        try:
            return Survey.objects.get(registry=self.registry,
                                      name=self.survey_name)
        except Survey.DoesNotExist:
            logger.error("No survey with name %s " % self.survey_name)


class SurveyRequest(models.Model):
    """
    This gets created on the clinical system
    """
    SURVEY_REQUEST_STATES = (
        (SurveyRequestStates.CREATED, "Created"),
        (SurveyRequestStates.REQUESTED, "Requested"),
        (SurveyRequestStates.RECEIVED, "Received"),
        (SurveyRequestStates.ERROR, "Error"))
    COMMUNICATION_TYPES = (
        (CommunicationTypes.QRCODE, "QRCode"),
        (CommunicationTypes.EMAIL, "Email"))
    registry = models.ForeignKey(Registry, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    survey_name = models.CharField(max_length=80)
    patient_token = models.CharField(max_length=80, unique=True, default=generate_token)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    user = models.CharField(max_length=80)  # username
    state = models.CharField(max_length=20, choices=SURVEY_REQUEST_STATES, default="created")
    error_detail = models.TextField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)
    communication_type = models.CharField(max_length=10, choices=COMMUNICATION_TYPES, default="qrcode")

    def send(self):
        logger.debug("sending request ...")
        if self.state == SurveyRequestStates.REQUESTED:
            try:
                self._send_proms_request()
                logger.debug("sent request to PROMS system OK")

            except PromsRequestError as pre:
                logger.error("Error sending survey request %s: %s" % (self.pk,
                                                                      pre))
                self._set_error(pre)
                return False

            if (self.communication_type == 'email'):
                try:
                    logger.debug("sending email to patient ...")
                    self._send_email()
                    logger.debug("sent email to patient OK")

                    return True
                except PromsEmailError as pe:
                    logger.error("Error emailing survey request %s: %s" % (self.pk,
                                                                           pe))
                    self._set_error(pe)
                    return False

    def _send_proms_request(self):
        from django.conf import settings

        logger.debug("sending request to proms system")
        proms_system_url = self.registry.metadata.get("proms_system_url", None)
        if proms_system_url is None:
            raise PromsRequestError("No proms_system_url defined in registry metadata %s" % self.registry.code)

        api = "/api/proms/v1/surveyassignments"
        api_url = proms_system_url + api
        logger.debug("api_url = %s" % api_url)

        survey_assignment_data = self._get_survey_assignment_data()
        headers = {'PROMS_SECRET_TOKEN': settings.PROMS_SECRET_TOKEN}

        response = requests.post(api_url,
                                 data=survey_assignment_data,
                                 headers=headers)
        logger.debug("response code %s" % response.status_code)
        self.check_response_for_error(response)
        logger.debug("posted data")

    def _get_survey_assignment_data(self):
        packet = {}
        packet["registry_code"] = self.registry.code
        packet["survey_name"] = self.survey_name
        packet["patient_token"] = self.patient_token
        packet["state"] = "requested"
        packet["response"] = "{}"
        return packet

    def _set_error(self, msg):
        logger.debug("Error message %s" % msg)
        self.state = SurveyRequestStates.ERROR
        self.error_detail = msg
        self.save()

    def check_response_for_error(self, response):
        if (status.is_success(response.status_code) and response.status_code == status.HTTP_201_CREATED):
            logger.debug("Survey request Created")
            return True

        if (status.is_success(response.status_code)):
            logger.debug("Error with other status %s" % response.status_code)
            self._set_error("Error with other status %s" % response)
            raise PromsRequestError("Error with code %s" % response.status_code)

        if (status.is_client_error(response.status_code)):
            logger.debug("Client Error %s" % response.status_code)
            self._set_error("Client Error %s" % response)
            raise PromsRequestError("Client Error with code %s" % response.status_code)
        elif (status.is_server_error(response.status_code)):
            logger.debug("Server error %s" % response.status_code)
            self._set_error("Server error %s" % response)
            raise PromsRequestError("Server error with code %s" % response.status_code)

    @property
    def email_link(self):
        # https://rdrf.ccgapps.com.au/cicproms/promslanding?t=foo23&r=ICHOMCRC&s=smap
        proms_system_url = self.registry.proms_system_url

        landing_page = "/promslanding?t=%s&r=%s&s=%s" % (self.patient_token,
                                                         self.registry.code,
                                                         self.survey_name)

        return proms_system_url + landing_page

    @property
    def name(self):
        return "%s %s Survey" % (self.registry.name,
                                 self.survey_name)

    def _send_email(self):
        logger.debug("sending email to user with link")
        try:
            emailer = Notifier()
            subject_line = "%s %s Survey Request" % (self.registry.name,
                                                     self.survey_name)
            email_body = "Please use the following link to take the %s survey: %s" % (self.name,
                                                                                      self.email_link)

            emailer.send_email(self.patient.email,
                               subject_line,
                               email_body)

        except NotificationError as nerr:
            raise PromsEmailError(nerr)
        except Exception as ex:
            raise PromsEmailError(ex)

    @property
    def qrcode_link(self):
        return reverse('promsqrcode', args=[self.patient_token])

    @property
    def patient_name(self):
        return "%s %s" % (self.patient.given_names,
                          self.patient.family_name)

    @property
    def survey(self):
        try:
            return Survey.objects.get(registry=self.registry,
                                      name=self.survey_name)
        except Survey.DoesNotExist:
            logger.error("No survey with name %s " % self.survey_name)
