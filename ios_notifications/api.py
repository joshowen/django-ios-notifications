# -*- coding: utf-8 -*-

from django.http import HttpResponseNotAllowed, QueryDict
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator

from ios_notifications.models import Device
from ios_notifications.forms import DeviceForm
from ios_notifications.decorators import api_authentication_required
from ios_notifications.http import HttpResponseNotImplemented, JSONResponse

from sentry.client.models import client as sentry_client

class BaseResource(object):
    """
    The base class for any API Resources.
    """
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')

    @method_decorator(api_authentication_required)
    @csrf_exempt
    def route(self, request, **kwargs):
        #sentry_client.create_from_text("Method:" + request.method + "\n\nPOST:" + str(request.POST) + "\n\nGET:" + str(request.GET))

        method = request.method
        if method in self.allowed_methods:
            if hasattr(self, method.lower()):
                if method == 'PUT':
                    request.PUT = QueryDict(request.raw_post_data).copy()
                return getattr(self, method.lower())(request, **kwargs)

            return HttpResponseNotImplemented()

        return HttpResponseNotAllowed(self.allowed_methods)


class DeviceResource(BaseResource):
    """
    The API resource for ios_notifications.models.Device.

    Allowed HTTP methods are GET, POST and PUT.
    """
    allowed_methods = ('GET', 'POST', 'PUT')

    def get(self, request, **kwargs):
        """
        Returns an HTTP response with the device in serialized JSON format.
        The device token and device service are expected as the keyword arguments
        supplied by the URL.

        If the device does not exist a 404 will be raised.
        """

        if "token" in kwargs.keys() and "service_id" in kwargs.keys():
            devices = Device.objects.filter(token=kwargs.get('token'),
                                            service__id=int(kwargs.get('service_id', 0)))
            if devices.exists():
                device = devices.get()
                return JSONResponse(device)
            
        return JSONResponse({}, status=404)

    def post(self, request, **kwargs):
        """
        Creates a new device or updates an existing one to `is_active=True`.
        Expects two non-options POST parameters: `token` and `service`.
        """
        devices = Device.objects.filter(token=request.POST.get('token'),
                                        service__id=int(request.POST.get('service', 0)))
        if devices.exists():
            device = devices.get()
            device.is_active = True

            #conditionally set other data
            device.platform = request.POST.get("platform", None)
            device.display = request.POST.get("display", None)
            device.os_version = request.POST.get("os_version", None)
            
            device.save()
            return JSONResponse(device)
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.is_active = True

            #conditionally set other data
            device.platform = request.POST.get("platform", None)
            device.display = request.POST.get("display", None)
            device.os_version = request.POST.get("os_version", None)

            device.save()
            return JSONResponse(device, status=201)
        return JSONResponse(form.errors, status=400)

    def put(self, request, **kwargs):
        """
        Updates an existing device.

        If the device does not exist a 404 will be raised.

        The device token and device service are expected as the keyword arguments
        supplied by the URL.

        Any attributes to be updated should be supplied as parameters in the request
        body of any HTTP PUT request.
        """
        try:
            device = Device.objects.get(**kwargs)
        except Device.DoesNotExist:
            return JSONResponse({'error': 'Device with token %s and service %s does not exist' %
                                (kwargs['token'], kwargs['service__id'])}, status=400)

        if 'users' in request.PUT:
            try:
                user_ids = request.PUT.getlist('users')
                device.users.remove(*[u.id for u in device.users.all()])
                device.users.add(*User.objects.filter(id__in=user_ids))
            except (ValueError, IntegrityError) as e:
                return JSONResponse({'error': e.message}, status=400)
            del request.PUT['users']

        for key, value in request.PUT.items():
            setattr(device, key, value)
        device.save()

        return JSONResponse(device)


class Router(object):
    """
    A simple class for handling URL routes.
    """
    def __init__(self):
        self.device = DeviceResource().route

routes = Router()
