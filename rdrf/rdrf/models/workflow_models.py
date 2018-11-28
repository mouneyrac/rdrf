from django.db import models
from rdrf.models.definition.models import Registry
from registry.groups.models import CustomUser
from datetime import datetime
from rdrf.helpers.utils import generate_token
from rdrf.services.io.notifications.email_notification import process_notification
from rdrf.events.events import EventType
from django.core.urlresolvers import reverse

import logging

logger = logging.getLogger(__name__)

class ClinicianSignupRequest(models.Model):
    STATES = (("emailed", "Emailed"),      # clinician emailed
              ("signed-up", "Signed Up"),  # the clinician accepted the request and a user object was created
              ("activated", "Activated"),  # the clinician activated
              ("created", "Created"),      # request created but nothing sent yet
              ("error", "Error"),          # error
              ("rejected", "Rejected"))    # the clinician received the request but rejected it
    
    registry = models.ForeignKey(Registry)
    patient_id = models.IntegerField()   # the patient id whose clinician it is ( had import issues with Patient)
    clinician_email = models.CharField(max_length=80)
    state = models.CharField(max_length=80, choices=STATES, default="created")
    token = models.CharField(max_length=80, default=generate_token, unique=True)
    clinician_other = models.ForeignKey("patients.ClinicianOther")  # this is the model the parent creates with data about the clinician`1
    clinician = models.ForeignKey(CustomUser, blank=True, null=True)
    emailed_date = models.DateTimeField(null=True)
    signup_date = models.DateTimeField(null=True)

    def send_request(self):
        self._send_email()
        self.state = "emailed"
        self.emailed_date = datetime.now()
        self.save()

    def _send_email(self):
        from registry.patients.models import Patient
        from registry.patients.models import ParentGuardian
        
        patient = Patient.objects.get(id=self.patient_id)
        try:
            parent = ParentGuardian.objects.get(patient=patient)
            participant_name = "%s %s" % (parent.first_name, parent.last_name)
        except ParentGuardian.DoesNotExist:
            participant_name = "No parent"
            
        patient_name = "%s %s" % (patient.given_names, patient.family_name)
        if self.clinician_other.speciality:
            speciality = self.clinician_other.speciality.name
        else:
            speciality = "Unspecified"

        template_data = {"speciality": speciality,
                         "clinician_last_name": self.clinician_other.clinician_name,
                         "participant_name": participant_name,
                         "clinician_email": self.clinician_other.clinician_email,
                         "patient_name": patient_name,
                         "registration_link": self._construct_registration_link()}

        process_notification(self.registry.code,
                             EventType.CLINICIAN_SIGNUP_REQUEST,
                             template_data)

    def _construct_registration_link(self):
        """
        Return a link which will be sent to a clinician to activate ( become a user)
        """
        from rdrf.helpers.utils import get_site
        
        site_url = get_site()
        return site_url + reverse("registration_register", args=(self.registry.code,)) + "?t=%s" % self.token

    def _get_participant(self):
        try:
            # to do
            pass
        except:
            pass

    def notify_participant(self):
        if self.state != "activated":
            raise Exception("Participant can be notified only after activation of clinician")
        participant = self._get_participant()
        
        template_data = {}
        
        process_notification(self.registry.code,
                             EventType.PARTICIPANT_CONFIRMATION,
                             template_data)


    @staticmethod
    def create(registry_model, patient_model, clinician_other, clinician_email):
        csr = ClinicianSignupRequest(registry=registry_model,
                                     patient_id=patient_model.pk,
                                     clinician_other=clinician_other,
                                     clinician_email=clinician_email)
        csr.save()
        logger.debug("created ClinicianSignUpRequest OK")
        return csr
