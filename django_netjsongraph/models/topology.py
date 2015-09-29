import json
from collections import OrderedDict
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible
from django.utils.module_loading import import_string

from uuidfield import UUIDField
from netdiff import diff, NetJsonParser

from ..base import TimeStampedEditableModel
from ..settings import PARSERS


@python_2_unicode_compatible
class BaseTopology(TimeStampedEditableModel):
    id = UUIDField(auto=True, primary_key=True)
    label = models.CharField(_('label'), max_length=64)
    parser = models.CharField(_('format'), choices=PARSERS,
                                           max_length=128,
                                           help_text=_('Select topology format'))
    url = models.URLField(_('url'), help_text=_('Topology data will be fetched from this URL'))

    # the following fields will be filled automatically
    protocol = models.CharField(_('protocol'), max_length=64, blank=True)
    version = models.CharField(_('version'), max_length=24, blank=True)
    revision = models.CharField(_('revision'), max_length=64, blank=True)
    metric = models.CharField(_('metric'), max_length=24, blank=True)

    class Meta:
        verbose_name_plural = _('topologies')
        abstract = True

    def __str__(self):
        return self.label

    _parser_class = None

    @property
    def parser_class(self):
        if not self._parser_class:
            self._parser_class = import_string(self.parser)
        return self._parser_class

    @property
    def latest(self):
        return self.parser_class(self.url, timeout=5)

    def diff(self):
        """ shortcut to netdiff.diff """
        latest = self.latest
        current = NetJsonParser(self.json(dict=True))
        return diff(current, latest)

    def json(self, dict=False, **kwargs):
        """ returns a dict that represents a NetJSON NetworkGraph object """
        nodes = []
        links = []

        for link in self.link_set.all():
            # append source node
            source_addresses = self.source.local_addresses
            source = {'id': source_addresses[0]}
            if len(source_addresses) > 1:
                source['local_addresses'] = source_addresses[1:]
            nodes.append(source)
            # append target node
            target_addresses = self.target.local_addresses
            target = {'id': target_addresses[0]}
            if len(target_addresses) > 1:
                target['local_addresses'] = target_addresses[1:]
            nodes.append(target)
            # append links
            links.append(OrderedDict((
                ('source', source['id']),
                ('target', source['id']),
                ('cost', link.cost)
            )))

        netjson = OrderedDict((
            ('type', 'NetworkGraph'),
            ('protocol', self.parser_class.protocol),
            ('version', self.parser_class.version),
            ('metric', self.parser_class.metric),
            ('nodes', nodes),
            ('links', links)
        ))

        if dict:
            return netjson

        return json.dumps(netjson, **kwargs)