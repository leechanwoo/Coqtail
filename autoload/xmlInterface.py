# -*- coding: utf8 -*-
"""
File: xmlInterface.py
Author: Wolf Honore

Description: Handles differences in the Coqtop XML interface across versions
and provides a uniform interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import re
import xml.etree.ElementTree as ET
from collections import namedtuple
try:
    unicode == str
except NameError:
    # If in python 3 make unicode an alias for str
    unicode = str


# Coqtop Response Types #
class Ok(object):
    """A response representing success."""

    def __init__(self, val, msg=''):
        """Initialize values."""
        self.val = val
        self.msg = msg

    def __str__(self):
        """Return the message field."""
        return self.msg

    @staticmethod
    def is_ok():
        """Check if this is a success response."""
        return True


class Err(object):
    """A response representing failure."""

    def __init__(self, msg, loc=(-1, -1), timed_out=False):
        """Initialize values."""
        self.msg = msg
        self.loc = loc
        self.timed_out = timed_out

    def __str__(self):
        """Return the message field."""
        return self.msg

    @staticmethod
    def is_ok():
        """Check if this is a success response."""
        return False


# Coqtop Types #
Option = namedtuple('Option', ['val'])

Inl = namedtuple('Inl', ['val'])
Inr = namedtuple('Inr', ['val'])

Goal = namedtuple('Goal', ['id', 'hyp', 'ccl'])
Goals = namedtuple('Goals', ['fg', 'bg', 'shelved', 'given_up'])
Evar = namedtuple('Evar', ['info'])

OptionState = namedtuple('OptionState', ['sync', 'depr', 'name', 'value'])
OptionValue = namedtuple('OptionValue', ['val'])

StateId = namedtuple('StateId', ['id'])
Status = namedtuple('Status', ['path', 'proofname', 'allproofs', 'proofnum'])
CoqInfo = namedtuple('CoqInfo', ['coq_version',
                                 'protocol_version',
                                 'release_data',
                                 'compile_data'])

# All the Coqtop namedtuples
namedtuples = (Option, Inl, Inr, Goal, Goals, Evar, OptionState, OptionValue,
               StateId, Status, CoqInfo)

# The error in case of a timeout
TIMEOUT_ERR = Err('Coq timed out. You can change the timeout with '
                  '<leader>ct and try again.',
                  timed_out=True)


# Helpers #
def unexpected(expected, got):
    """Raise an exception with a message showing what was expected."""
    raise ValueError("Expected {}, but got {}".format(' or '.join(expected),
                                                      got))


def is_tuple(val):
    """Check that val is a tuple, but not one of the Coqtop namedtuples."""
    return isinstance(val, tuple) and not isinstance(val, namedtuples)


class XmlInterfaceBase(object):
    """Provide methods common to all XML interface versions."""

    def _build_xml(self, tag, val=None, children=None):
        """Construct an xml element with a given tag, value, and children."""
        attribs = {'val': val} if val is not None else {}

        # If children is a list then convert each element separately, if it is
        # a tuple, treat it as a single element
        if children is None:
            children = ()
        elif isinstance(children, list):
            children = [self._from_value(child) for child in children]
        else:
            children = (self._from_value(children),)

        xml = ET.Element(tag, attribs)
        xml.extend(children)

        return xml

    @staticmethod
    def _unescape(cmd):
        """Replace escaped characters with the unescaped version."""
        charmap = {
            b'&nbsp;': b' ',
            b'&apos;': b'\'',
            b'&#40;': b'(',
            b'&#41;': b')'
        }

        for escape, unescape in charmap.items():
            cmd = cmd.replace(escape, unescape)

        return cmd


class XmlInterface86(XmlInterfaceBase):
    """The version 8.6.* XML interface."""

    # XML Parsing and Marshalling #
    def _to_response(self, xml):
        """Parse an xml response into an Ok or Err."""
        assert xml.tag == 'value'

        val = xml.get('val')
        if val == 'good':
            return Ok(self._to_value(xml[0]))
        elif val == 'fail':
            loc_s = int(xml.get('loc_s', -1))
            loc_e = int(xml.get('loc_e', -1))

            msg = ''.join(xml.itertext())

            return Err(msg, (loc_s, loc_e))
        else:
            unexpected(('good', 'fail'), val)

    def _to_value(self, xml):
        """Parse an xml value into a corresponding Python type."""
        tag = xml.tag

        if tag == 'unit':
            # <unit />
            return ()
        elif tag == 'bool':
            # <bool val="true|false" />
            val = xml.get('val')

            if val == 'true':
                return True
            elif val == 'false':
                return False
            else:
                unexpected(('true', 'false'), val)
        elif tag == 'int':
            # <int>int</int>
            return int(xml.text)
        elif tag in ('string', 'richpp'):
            # <string>str</string>
            # <richpp>str</richpp>
            return ''.join(xml.itertext())
        elif tag == 'list':
            # <list>(val)*</list>
            return list(map(self._to_value, xml))
        elif tag == 'pair':
            # <pair>val1 val2</pair>
            return tuple(map(self._to_value, xml))
        elif tag == 'option':
            # <option val="some">val</option> | <option val="none" />
            val = xml.get('val')

            if val == 'none':
                return Option(None)
            elif val == 'some':
                return Option(self._to_value(xml[0]))
            else:
                unexpected(('none', 'some'), val)
        elif tag == 'union':
            # <union val="in_l|in_r">val</union>
            val = xml.get('val')

            if val == 'in_l':
                return Inl(self._to_value(xml[0]))
            elif val == 'in_r':
                return Inr(self._to_value(xml[0]))
            else:
                unexpected(('in_l', 'in_r'), val)
        elif tag == 'goal':
            # <goal>string (list Pp) Pp</goal>
            return Goal(*map(self._to_value, xml))
        elif tag == 'goals':
            # <goals>(list goal) (list (list goal * list goal)) (list goal) (list goal)</goals>
            return Goals(*map(self._to_value, xml))
        elif tag == 'evar':
            # <evar>string</evar>
            return Evar(self._to_value(xml[0]))
        elif tag == 'option_state':
            # <option_state>bool bool string option_value</option_state>
            return OptionState(*map(self._to_value, xml))
        elif tag == 'option_value':
            # <option_value>bool|option int|string|option string</option_value>
            return OptionValue(self._to_value(xml[0]))
        elif tag == 'state_id':
            # <state_id val="int" />
            return StateId(int(xml.get('val')))
        elif tag == 'status':
            # <status>(list string) (option string) (list string) int</string>
            return Status(*map(self._to_value, xml))
        elif tag == 'coq_info':
            # <coq_info>string string string string</coq_info>
            return CoqInfo(*map(self._to_value, xml))
        elif tag == 'message':
            # <message>message_level (option ?) richpp</message>
            # TODO: see if option or message_level are useful
            return self._to_value(xml.find('richpp'))
        else:
            unexpected((), tag)

    def _from_value(self, val):
        """Construct an xml element from a corresponding Python type."""
        if val == ():
            return self._build_xml('unit')
        elif isinstance(val, bool):
            xml = self._build_xml('bool', str(val).lower())
            return xml
        elif isinstance(val, int):
            xml = self._build_xml('int')
            xml.text = str(val)
            return xml
        elif isinstance(val, (str, unicode)):
            xml = self._build_xml('string')
            xml.text = val
            return xml
        elif isinstance(val, list):
            return self._build_xml('list', None, val)
        elif is_tuple(val):
            return self._build_xml('pair', None, [val[0], val[1]])
        elif isinstance(val, Option):
            if val.val is not None:
                return self._build_xml('option', 'some', val.val)
            else:
                return self._build_xml('option', 'none')
        elif isinstance(val, Inl):
            return self._build_xml('union', 'in_l', val.val)
        elif isinstance(val, Inr):
            return self._build_xml('union', 'in_r', val.val)
        elif isinstance(val, StateId):
            return self._build_xml('state_id', str(val.id))
        else:
            unexpected((), type(val))

    # Coqtop Commands #
    def init(self, *args, **kwargs):
        """Create an XML string for the 'Init' command."""
        # Args:
        #   option string - A Coq file to add to the LoadPath to do ?
        return ET.tostring(self._build_xml('call', 'Init', Option(None)),
                           kwargs.get('encoding', 'utf-8'))

    def add(self, cmd, state, *args, **kwargs):
        """Create an XML string for the 'Add' command."""
        # Args:
        #   string - The command to evaluate
        #   int - The editId ?
        #   state_id - The current state_id
        #   bool - Verbose output
        return ET.tostring(self._build_xml('call',
                                           'Add',
                                           ((cmd, -1), (state, True))),
                           kwargs.get('encoding', 'utf-8'))

    def edit_at(self, state, *args, **kwargs):
        """Create an XML string for the 'Edit_at' command."""
        # Args:
        #   state_id - The state_id to move to
        return ET.tostring(self._build_xml('call', 'Edit_at', state),
                           kwargs.get('encoding', 'utf-8'))

    def query(self, cmd, state, *args, **kwargs):
        """Create an XML string for the 'Query' command."""
        # Args:
        #   string - The command to query
        #   state_id - The current state_id
        return ET.tostring(self._build_xml('call',
                                           'Query',
                                           (cmd, state)),
                           kwargs.get('encoding', 'utf-8'))

    def goal(self, *args, **kwargs):
        """Create an XML string for the 'Goal' command."""
        # Args:
        #   unit - Empty arg
        return ET.tostring(self._build_xml('call', 'Goal', ()),
                           kwargs.get('encoding', 'utf-8'))

    def raw_response(self, data):
        """Try to parse an XML response from Coqtop into an Ok or Err."""
        val = None
        msgs = []

        try:
            responses = ET.fromstring(b'<coqtoproot>' +
                                      self._unescape(data) +
                                      b'</coqtoproot>')
        except ET.ParseError:
            # If not all data has been read, the XML might not be well-formed
            return None

        # Wait for a 'value' node and store any 'message' nodes
        for response in responses:
            if response.tag == 'value':
                val = self._to_response(response)
            if response.tag == 'message':
                msgs.append(self._to_value(response))
            if response.tag == 'feedback':
                # TODO: handle feedback messages
                pass

        if val is not None:
            val.msg += '\n\n'.join(msgs)

        return val


def XmlInterface(version):
    """Return the appropriate XmlInterface class for the given version."""
    versions = version.replace('pl', '.').split('.')

    # Strip any trailing text (e.g. '+beta1')
    versions = tuple(int(re.match('[0-9]+', v).group(0)) for v in versions)
    versions += (0,) * (3 - len(versions))

    if (8, 6, 0) <= versions < (8, 7, 0):
        return XmlInterface86()
    else:
        raise ValueError("Invalid version: {}".format(version))