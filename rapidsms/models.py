#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.db import models
from .utils.modules import try_import, get_classes
from .conf import settings


class ExtensibleModelBase(models.base.ModelBase):
    def __new__(cls, name, bases, attrs):
        try:
            app_label = attrs['Meta'].app_label
        except KeyError:
            module_name = attrs["__module__"]
            app_label = module_name.split('.')[-2]
        extensions = _find_extensions(app_label, name)
        bases = tuple(extensions) + bases

        return super(ExtensibleModelBase, cls).__new__(
            cls, name, bases, attrs)


def _find_extensions(app_label, model_name):
    ext = []

    suffix = "extensions.%s.%s" % (
        app_label, model_name.lower())
    modules = filter(None, [
        try_import("%s.%s" % (app_name, suffix))
        for app_name in settings.INSTALLED_APPS])

    for module in modules:
        for cls in get_classes(module, models.Model):
            ext.append(cls)

    return ext


class Backend(models.Model):
    """
    This model isn't really a backend. Those are regular Python classes,
    in rapidsms/backends. This is just a stub model to provide a primary
    key for each running backend, so other models can be linked to it
    with ForeignKeys.
    """

    name = models.CharField(max_length=20, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)


class App(models.Model):
    """
    This model isn't really a RapidSMS App. Like Backend, it's just a
    stub model to provide a primary key for each app, so other models
    can be linked to it.

    The Django ContentType stuff doesn't quite work here, since not all
    RapidSMS apps are valid Django apps. It would be nice to fill in the
    gaps and inherit from it at some point in the future.

    Instances of this model are generated by the update_apps management
    command, (which is hooked on Router startup (TODO: webui startup)),
    and probably shouldn't be messed with after that.
    """

    module = models.CharField(max_length=100, unique=True)
    active = models.BooleanField()

    def __unicode__(self):
        return self.module

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)


class ContactBase(models.Model):
    name = models.CharField(max_length=100, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    # the spec: http://www.w3.org/International/articles/language-tags/Overview
    # reference:http://www.iana.org/assignments/language-subtag-registry
    language = models.CharField(max_length=6, blank=True,
                                help_text="The language which this contact "
                                "prefers to communicate in, as a W3C "
                                "language tag. If this field is left blank, "
                                "RapidSMS will default to: " +
                                settings.LANGUAGE_CODE)

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.name or "Anonymous"

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)

    @property
    def is_anonymous(self):
        return not self.name

    @property
    def default_connection(self):
        """
        Return the default connection for this person.
        """
        # TODO: this is defined totally arbitrarily for a future
        # sane implementation
        if self.connection_set.count() > 0:
            return self.connection_set.all()[0]
        return None


class Contact(ContactBase):
    __metaclass__ = ExtensibleModelBase


class ConnectionBase(models.Model):
    backend = models.ForeignKey(Backend)
    identity = models.CharField(max_length=100)
    contact = models.ForeignKey(Contact, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        unique_together = (('backend', 'identity'),)

    def __unicode__(self):
        return "%s via %s" %\
            (self.identity, self.backend)

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)


class Connection(ConnectionBase):
    """
    This model pairs a Backend object with an identity unique to it (eg.
    a phone number, email address, or IRC nick), so RapidSMS developers
    need not worry about which backend a messge originated from.
    """

    __metaclass__ = ExtensibleModelBase
