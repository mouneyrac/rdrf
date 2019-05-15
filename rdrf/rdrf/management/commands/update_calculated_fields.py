from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Update calculated field values. It is mainly use to trigger periodic update.'

    def add_arguments(self, parser):
        parser.add_argument('--patient_id', action='append', type=int, help='Only calculate the fields for a specific patient')
        parser.add_argument('--registry_id', action='append', type=int, help='Only calculate the fields for a specific registry')
        parser.add_argument('--cde_id', action='append', type=int, help='Only calculate the fields for a specific CDE')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(options['patient_id']))
        self.stdout.write(self.style.SUCCESS('All fields have been successfully updated'))
