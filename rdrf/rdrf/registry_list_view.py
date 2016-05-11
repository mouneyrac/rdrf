from django.shortcuts import render_to_response, RequestContext
from django.views.generic.base import View
from models import Registry


class RegistryListView(View):

    def get(self, request):
        context = {}
        context['registrys'] = [r for r in Registry.objects.all()]
        return render_to_response(
            'rdrf_cdes/portfolio.html',
            context,
            context_instance=RequestContext(request))