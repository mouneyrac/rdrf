.. _gui:

RDRF Graphical User Interface
=============================

RDRF is a Django web application and accessed via any web browser (f.g. Chrome or Firefox).

The system uses the standard Django views (generic class-based views) with bootstrap-styling to provide access to the application.

As an admin user, regularly used links are  links are accessed via "Settings", while the "Admin Page" contains the complete list of links.


Admin Page
----------

The Admin Page consists of:

Patient List
------------
Add or edit patient information (contact details) 

Doctors
-------
Add or edit Doctors

Reports
-------
Access Reports that have been defined with the Explorer tool

Users
-----
Add or edit users

Genes
-----
Add or edit genes

Laboratories
-------------
Add or edit laboratories

Registries
-------------
Add or edit registries

Registry Form
-------------
Add or edit forms (created forms are accessed under 'Modules' in the Patient List)

Sections
--------
Add or edit sections (Sctions are compiled into Forms)

Data Elements
-------------
Add or edit CDEs (CDEs are compiled into sections)

Permissible Value Groups
------------------------
Add or edit PVGs

Permissible Values
------------------------
Add or edit PVs (assigned to a pemritted value group)

Groups
------
Administer available permissions for user groups (working group curators, clinicians, etc)

Importer
--------
Import a registry definition (yaml file)

Demographics Fields
-------------------
Configure Demographics fields to be hidden or readonly by registry and group

Working Groups
--------------
Add or edit working groups (e.g. States, Hospitals, Clinics)

Questionnaire Responses
-----------------------
Questionnaire responses are stored here when submitted by a patient, awaiting validation or rejection by an admin or curator
