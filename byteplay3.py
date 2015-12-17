'''
                        byteplay3.py

byteplay is a module supporting the disassembly, modification, and re-assembly
of Python bytecode objects.

Expected use:
    import byteplay3 as bp
    myfunc_code = bp.Code( myfunc.__code__ )
    # manipulate myfunc_code using bp. members...
    myfunc.__code__ = myfunc_code.to_code()

The following names are available from the module:
    Classes:

        Code
            An object that stores the properties of of a Python code object.
            The class method Code.from_code(code_object) returns a Code
            object. The object method to_code() returns a code object from
            the contents of the Code object. See the class docstring below
            for many more features.

        Opcode
            An int, the value of a Python bytecode verb, but its __str__
            value is the name of the opcode, e.g. "LOAD_FAST" for 3.

        CodeList
            An expanded form of a Python bytecode string: a list of
            (Opcode, argument) tuples. A Code object .code member is
            a CodeList, just as the co_code member of a code object is
            a bytestring of opcodes.

        Label
            Class of a minimal object used in a CodeList, where a tuple
            (Label,None) marks a jump target in the list. Discarded
            when to_code() re-creates the code object.

    Global vars:

        cmp_op
            a tuple of the Python comparison operator names such as "<="
            and "is not"; the strings that can appear as the argument of
            the COMPARE_OP bytecode. From the standard module "opcode".

        SetLineno
            Global var holding the single object of the SetLinenoType
            class. (SetLineno, line_number) in a CodeList marks the
            beginning of code from source line_number.

        opmap
            A dict of { 'OPCODE_NAME' : Opcode } for all valid bytecodes.

        opname
            Inverse of opmap, { Opcode : 'OPCODE_NAME }

        opcodes
            A set of valid Opcodes, for quick testing (x in opcodes...)

        The following are sets of Opcodes used for fast tests of opcode
        features, "if oc in hasarg..."

        hasarg     opcodes that take an argument
        hascode    opcodes that take a code object argument
        hascompare opcodes that take one of cmp_op
        hasjabs    opcodes that jump to an absolute bytecode offset
        hasjrel    opcodes that jump to a relative offset
        hasjump    union of preceding two sets
        haslocal   opcodes that refer to a local e.g. STORE_FAST
        hasname    opcodes that refer to a var by name
        hasfree    opcodes that refer to a "free" var
        hasflow    opcodes that cause nonsequential execution

        POP_TOP=Opcode(1)
        ... etc ...
        LOAD_CLASSDEREF=Opcode(148)
            *ALL* Python opcode names are added to the globals of this
            module, with values as OpCode objects. The same names are
            available from the standard module "opcode" valued as ints.

    Functions:

        getse( opcode, arg=None )
            given an opcode number and the opcode's argument if any,
            return the stack effect of that opcode as a (pop_item_count,
            push_item_count) tuple.            .

        isopcode( opcode )
            true when opcode is a Python-defined opcode and not one
            of the two convenience values Label and SetLineno.

        printcodelist( CodeList_object, to=sys.stdout )
            print a disassembly of the code in CodeList_object to the
            default output stream or a specified file object.

'''

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Establish version and other import dunder-constants.

__license__ = '''
                 License (GPL-3.0) :
    This file is part of the byteplay module.
    byteplay is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This module is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You can find a copy of the GNU General Public License in the file
    COPYING.TXT included in the distribution of this module, or see:
    <http://www.gnu.org/licenses/>.
'''
__version__ = "3.0.0"
__author__  = "Noam Yorav-Raphael (Python 2); David Cortesi (Python 3 mods)"
__copyright__ = "Copyright (C) 2006-2010 Noam Yorav-Raphael; Python3 modifications (C) 2016 David Cortesi"
__maintainer__ = "David Cortesi"
__email__ = "davecortesi@gmail.com"


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# The __all__ global establishes the complete API of the module on import.
# "from byteplay import *" imports these names (plus a bunch of opcode-names,
# see below):

__all__ = ['cmp_op',
           'Code',
           'CodeList',
           'getse',
           'hasarg',
           'hascode',
           'hascompare',
           'hasjabs',
           'hasjrel',
           'hasjump',
           'haslocal',
           'hasname',
           'hasfree',
           'hasflow',
           'isopcode',
           'Label',
           'Opcode',
           'opmap',
           'opname',
           'opcodes',
           'printcodelist',
           'SetLineno'
           ]

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Because this module uses a number of standard modules that are not
# commonly used in typical code, some import statements are annotated.

import sys
from io import StringIO
import itertools # used for .izip()

# An array('B') object is used to represent a bytecode string when creating a
# code object, see to_code()

from array import array

import types # used for CodeType only

import operator # names for standard operators such as __eq__

# The opcode module is standard, distributed in lib/python3.v, but is NOT
# documented in docs.python.org/3.v/*. It says it is "shared between dis and
# other modules which operate on bytecodes". Anyway, opcode defines all
# the bytecodes and their attributes under various names.
#
# Byteplay basically plunders opcode and re-creates its exported names with
# more information or different organization, which is discussed in the
# comments below. Byteplay recreates two of opcode's globals,
# opcode.opname and opcode.opmap, in a different form.

import opcode

# From the standard module dis grab this function, defined as "Detect all
# offsets in a byte code which are jump targets. Return the list of offsets."

from dis import findlabels

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Check the Python version. We support 3.x only.

python_version = '.'.join(str(x) for x in sys.version_info[:2])
if sys.version_info[0] != 3 :
    print( "This version of BytePlay requires Python 3.x", file=sys.stderr )

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Define opcodes and information about them, basically extending the values
# presented by module opcode. The global opname is established just below.

class Opcode(int):
    """
    An int which represents an opcode but has a nicer __repr__ and __str__.
    """
    def __repr__(self):
        return opname[self]
    __str__ = __repr__

# opcode.opmap is a dict of { "op_name" : op_int_value }. Here we make our
# own opmap in which op_int_value is an Opcode object rather than a simple
# int. Also, leave out 'EXTENDED_ARG'/144, which is apparently special as it
# is listed seperately in opcode.py.

opmap = dict( [ (name, Opcode(bytecode) )
              for name, bytecode in opcode.opmap.items()
              if name != 'EXTENDED_ARG'
              ] )

# opname is the inverse of opmap, dict { op_int_value : "op_name" }.
# (This is quite different from opcode.opname which is only a list.)

opname = dict((bytecode, name) for name, bytecode in opmap.items())

# opcodes is a set of the keys of dict opname, hence of valid bytecode
# values, for quick testing.

opcodes = set( opname.keys() )

# Now force all opcode names into our global namespace, so e.g. POP_TOP is a
# global variable with value Opcode(1).
#
# The names of these globals are also added to global __all__ (defined above)
# so they are part of our API.
#
# TODO: Really? We need this? and need to export them in __all__?

for name, code in opmap.items():
    globals()[name] = code
    __all__.append(name)

# Add opcode.cmp_op to our API (the name "cmp_op" is in __all__ already). It
# is a tuple of the Python comparison operator names such as "<=" and "is
# not". These are the strings that can appear as the argument value of the
# COMPARE_OP bytecode.

cmp_op = opcode.cmp_op

# Make sets of Opcode objects that have particular properties. Each of these
# "hasxxx" names is in our API __all__.
#
# Set of the opcodes that...
#
# ... take a cmp_op as their argument (only COMPARE_OP):

hascompare = set(Opcode(x) for x in opcode.hascompare)

# ... HAVE_ARGUMENT, which is all those above 90 (currently). "x in hasarg"
# is a more readable test than "x >= HAVE_ARGUMENT"

hasarg = set(x for x in opcodes if x >= opcode.HAVE_ARGUMENT)

# ... have a constant argument (currently only 100=LOAD_CONST)

hasconst = set(Opcode(x) for x in opcode.hasconst)

# ... have a name argument, e.g. LOAD_GLOBAL, DELETE_ATTR

hasname = set(Opcode(x) for x in opcode.hasname)

# ... have a relative-jump-target argument, e.g. FOR_ITER

hasjrel = set(Opcode(x) for x in opcode.hasjrel)

# ... have an absolute jump-target argument, e.g. JUMP_IF_FALSE_OR_POP

hasjabs = set(Opcode(x) for x in opcode.hasjabs)

# ... have any kind of jump (so much easier with sets not lists)

hasjump = hasjrel.union(hasjabs)

# ..refer to a local variable, e.g. STORE_FAST

haslocal = set(Opcode(x) for x in opcode.haslocal)

# ..refer to a "free" variable, e.g. LOAD_CLOSURE

hasfree = set(Opcode(x) for x in opcode.hasfree)

# ..have a code object for argument
# TODO: why not set(Opcode(x) for x in [MAKE_FUNCTION, MAKE_CLOSURE]) ?
#       is it a problem that other sets are Opcodes and this is ints?

hascode = set([MAKE_FUNCTION, MAKE_CLOSURE])


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# A CodeList is an expanded version of a Python code byte-string.
#
# The contents of a CodeList is a series of tuples (Opcode, argument) where
# Opcode is an Opcode object based on the bytecode, and argument is either
# None or the actual argument value of the opcode.
#
# Argument values are typically integers, but they can be any type of
# constant, for example if a function defines an inner function, one of its
# first opcodes is (LOAD_CONST, <python code object>) where the constant
# value is an entire code object, in effect a large byte array.
#
# The __str__() result of a CodeList is a formatted disassembly as a list of
# strings, one line per bytecode. The printcodelist() function writes the
# list to a file.
#
# Internally to Python, a code object stores metadata about a bytestring and
# has a member co_code which is that byte-string. In the same way, here, a
# Code object (defined below) has metadata about a byte-string stored in a
# CodeList.
#

class CodeList(list):
    """
    A list for storing opcode tuples that has a nicer __str__()
    result, in fact, a formatted assembly listing.
    """

    def __str__(self):
        """
    Convert the current contents into a nice disassembly in multiple
    lines, in the manner of dis.dis. Here is a random sample:

    2           0 SETUP_LOOP              24 (to 27)
                3 LOAD_FAST                0 (L)
                6 GET_ITER
          >>    7 FOR_ITER                16 (to 26)
               10 STORE_FAST               1 (item)

        """
        output = [] # list of strings being created

        labeldict = {}
        pendinglabels = []
        # TODO SwearToGod I do not get this must study
        for i, ( op, arg ) in enumerate( self ):
            if isinstance(op, Label):
                pendinglabels.append( op )
            elif op is SetLineno:
                pass
            else:
                while pendinglabels:
                    labeldict[ pendinglabels.pop() ] = i

        lineno = None
        islabel = False
        for i, ( op, arg ) in enumerate( self ):
            if op is SetLineno:
                # This code item is a marker of a source line number, which is
                # not a bytecode. Set up so that the NEXT opcode will display the
                # line number in the left margin. Output a blank line here.
                lineno = arg    # note line number value
                output.append('') # insert the blank line
                continue # the loop

            if isinstance(op, Label):
                # This code item is a label marker, which is not a real Python
                # bytecode. It doesn't display in the output but it does
                # condition the NEXT opcode to have a ">>" marker.
                islabel = True
                continue # the loop without any output

            # Set up the current line number, if any, or a null string, to
            # print to the left of this item. In case it was a line number,
            # clear the flag.
            linenostr =  str(lineno) if lineno else ''
            lineno = None

            # Set up the ">>" jump-target marker if this code item is a
            # target, and clear that flag.
            islabelstr = '>>' if islabel else ''
            islabel = False

            # Set up the argument value to follow the opcode on the same line.
            if op in hasconst:
                # argument is const
                argstr = repr(arg)
            elif op in hasjump:
                # argument is jump target
                if arg in labeldict :
                    argstr = 'to ' + str( labeldict[arg] )
                else :
                    argstr = repr( arg )
            elif op in hasarg:
                # argument is something
                argstr = str( arg )
            else:
                # nope, no argument needed
                argstr = ''

            line = '%3s     %2s %4d %-20s %s' % (
                linenostr,
                islabelstr,
                i,
                op,
                argstr
            )
            output.append( line )
        return output

def printcodelist(codelist, to=sys.stdout):
    '''
    Write the lines of the codelist string list to the given file, or to
    the default output.

    A little Python 3 problem: if the to-file is in binary mode, we need
    to encode the strings, else a TypeError will be raised. Obvious
    answer, test for 'b' in to.mode? Nope, only "real" file objects
    have a mode member. StringIO objects, and the variant StringIO used
    as default sys.stdout, do not have .mode.

    However all file-like objects that support string output DO have
    an encoding member. (StringIO has one that is an empty string, but
    they have it.) So, if hasattr(to,'encoding'), just shove the whole
    string into it. Otherwise, encode the string utf-8 and shove that
    bytestring into it. (See? Python 3 not so hard...)

    '''
    # Get the whole disassembly as a string.
    whole_thang = '\n'.join( str( codelist ) )
    # if necessary, encode it to bytes
    if not hasattr( to, 'encoding' ) :
        whole_thang = whole_thang.encode( 'UTF-8' )
    # send it on its way
    to.write( whole_thang )


# Besides real opcodes our CodeList object may feature two non-opcodes One is
# the Set Line Number action, represented by a single global object of its
# class (which is exported in __all__)...

class SetLinenoType(object):
    def __repr__(self):
        return 'SetLineno'
    self.__str__ = self.__repr__

SetLineno = SetLinenoType()

# Two, the Label type which represents the target of a jump. (There is no
# bytecode in a real codestring for this; it is implicit in the numeric
# arguments of "hasjump" opcodes. The class Label is also in __all__.

class Label(object):
    pass

# This boolean function allows distinguishing real opcodes in a CodeList from
# the two non-opcode types. Note this assumes there only ever exists the one
# instance of SetLineno, although there may be multiple Label objects.
#
# TODO: would this not be safer using "not isinstance(obj,SetLinenoType)"?

def isopcode(obj):
    """
    Return whether obj is an opcode - not SetLineno or Label
    """
    return obj is not SetLineno and not isinstance(obj, Label)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Set up tools for knowing the stack behavior of opcodes.
#
# Create a dict _se in which the keys are Opcodes and the values are tuples
# that show the effect of that operation on the stack.
#
# Each tuple in _se has two values. The first is the number of items that the
# opcode pops (so the number that must be on the stack before). The second is
# the number that it pushes (so, will be on the stack after).
#
# For example _se[POP_TOP] ==> (1,0), it pops one item, and pushes none.
#

class _se_facts:
    """
    A class used as a scratch-pad for making static definitions of the stack
    effects of opcodes.

    Taken from assembler.py by Phillip J. Eby
    (and somewhat modified, for example adding NOP, because Eby
    initializes his list of stack effects to all-(0,0) so need not
    specify any opcodes that have no stack effect).

    """

    NOP       = 0,0

    POP_TOP   = 1,0
    ROT_TWO   = 2,2
    ROT_THREE = 3,3
    ROT_FOUR  = 4,4
    DUP_TOP   = 1,2

    UNARY_POSITIVE = UNARY_NEGATIVE = UNARY_NOT = UNARY_CONVERT = \
        UNARY_INVERT = GET_ITER = LOAD_ATTR = 1,1

    IMPORT_FROM = 1,2

    BINARY_POWER = BINARY_MULTIPLY = BINARY_DIVIDE = BINARY_FLOOR_DIVIDE = \
        BINARY_TRUE_DIVIDE = BINARY_MODULO = BINARY_ADD = BINARY_SUBTRACT = \
        BINARY_SUBSCR = BINARY_LSHIFT = BINARY_RSHIFT = BINARY_AND = \
        BINARY_XOR = BINARY_OR = COMPARE_OP = 2,1

    INPLACE_POWER = INPLACE_MULTIPLY = INPLACE_DIVIDE = \
        INPLACE_FLOOR_DIVIDE = INPLACE_TRUE_DIVIDE = INPLACE_MODULO = \
        INPLACE_ADD = INPLACE_SUBTRACT = INPLACE_LSHIFT = INPLACE_RSHIFT = \
        INPLACE_AND = INPLACE_XOR = INPLACE_OR = 2,1

    SLICE_0, SLICE_1, SLICE_2, SLICE_3 = \
        (1,1),(2,1),(2,1),(3,1)
    STORE_SLICE_0, STORE_SLICE_1, STORE_SLICE_2, STORE_SLICE_3 = \
        (2,0),(3,0),(3,0),(4,0)
    DELETE_SLICE_0, DELETE_SLICE_1, DELETE_SLICE_2, DELETE_SLICE_3 = \
        (1,0),(2,0),(2,0),(3,0)

    STORE_SUBSCR = 3,0
    DELETE_SUBSCR = STORE_ATTR = 2,0
    DELETE_ATTR = STORE_DEREF = 1,0
    PRINT_NEWLINE = 0,0
    PRINT_EXPR = PRINT_ITEM = PRINT_NEWLINE_TO = IMPORT_STAR = 1,0
    STORE_NAME = STORE_GLOBAL = STORE_FAST = 1,0
    PRINT_ITEM_TO = 2,0

    LOAD_LOCALS = LOAD_CONST = LOAD_NAME = LOAD_GLOBAL = LOAD_FAST = \
        LOAD_CLOSURE = LOAD_DEREF = BUILD_MAP = 0,1

    DELETE_FAST = DELETE_GLOBAL = DELETE_NAME = 0,0

    EXEC_STMT = 3,0
    BUILD_CLASS = 3,1

    STORE_MAP = MAP_ADD = 2,0
    SET_ADD = 1,0

    #if   python_version == '2.4': we don't support these
        #YIELD_VALUE = 1,0
        #IMPORT_NAME = 1,1
        #LIST_APPEND = 2,0
    #elif python_version == '2.5':
        #YIELD_VALUE = 1,1
        #IMPORT_NAME = 2,1
        #LIST_APPEND = 2,0
    #elif python_version == '2.6':
        #YIELD_VALUE = 1,1
        #IMPORT_NAME = 2,1
        #LIST_APPEND = 2,0
    #elif python_version == '2.7':
        #YIELD_VALUE = 1,1
        #IMPORT_NAME = 2,1
        #LIST_APPEND = 1,0
    # assuming Python 3 same as 2.7 for these?
    YIELD_VALUE = 1,1
    IMPORT_NAME = 2,1
    LIST_APPEND = 1,0

# Now use the properties of _se_facts to create the _se dict.

_se = dict((op, getattr(_se_facts, opname[op]))
           for op in opcodes
           if hasattr(_se, opname[op]))

# At this point, _se is a dict with 64 entries. Subtracting opcodes with
# stack effects from the set of all opcodes produces the set which "has
# flow", which I think means, can cause non-sequential execution.
# TODO: does it? and if so why not hasflow==hasjump?
#

hasflow = opcodes - set(_se) - \
          set([CALL_FUNCTION, CALL_FUNCTION_VAR, CALL_FUNCTION_KW,
               CALL_FUNCTION_VAR_KW, BUILD_TUPLE, BUILD_LIST,
               UNPACK_SEQUENCE, BUILD_SLICE, DUP_TOP_TWO,
               RAISE_VARARGS, MAKE_FUNCTION, MAKE_CLOSURE])
#if python_version == '2.7':
    #hasflow = hasflow - set([BUILD_SET])
hasflow = hasflow - set([BUILD_SET])

# With all that set up, this function can return the (pop,push) stack
# tuple for an opcode. In some cases the behavior depends on the argument.

def getse(op, arg=None):
    """

    Get the stack effect of an opcode, as a (pop, push) tuple.

    If an arg is needed and is not given, a ValueError is raised.
    If op isn't a simple opcode, that is, the flow doesn't always continue
    to the next opcode, a ValueError is raised.

    """

    # A number (64) of opcodes are already defined in the _se dict.

    if op in _se :
        return _se[op]

    # Continue to opcodes with an effect that depends on arg

    if arg is None:
        raise ValueError("Opcode stack behaviour depends on arg")

    # TODO: explain this

    def get_func_tup(arg, nextra):
        if arg > 0xFFFF:
            raise ValueError("Can only split a two-byte argument")
        return (nextra + 1 + (arg & 0xFF) + 2*((arg >> 8) & 0xFF),
                1)

    if op == CALL_FUNCTION:
        return get_func_tup(arg, 0)
    elif op == CALL_FUNCTION_VAR:
        return get_func_tup(arg, 1)
    elif op == CALL_FUNCTION_KW:
        return get_func_tup(arg, 1)
    elif op == CALL_FUNCTION_VAR_KW:
        return get_func_tup(arg, 2)

    elif op == BUILD_TUPLE:
        return arg, 1
    elif op == BUILD_LIST:
        return arg, 1
    elif op == BUILD_SET:
        return arg, 1
    elif op == UNPACK_SEQUENCE:
        return 1, arg
    elif op == BUILD_SLICE:
        return arg, 1
    elif op == DUP_TOP_TWO: # TODO: what does this really do?
        return arg, arg*2
    elif op == RAISE_VARARGS:
        return 1+arg, 1
    elif op == MAKE_FUNCTION:
        return 1+arg, 1
    elif op == MAKE_CLOSURE:
        return 2+arg, 1
    else:
        raise ValueError("The opcode %r isn't recognized or has a special "\
              "flow control" % op)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Define the Code class, which represents a Python code object in a
# more accessible format -- see docstring below.

# Flags from code.h. These flags appear in the co_coflags member of the
# code object. When converting from a code object (from_code(), below)
# some of them are isolated and converted into Code object members.
# When recreating a code object from a Code one, the flags are created
# based on Code object members and contents.

CO_OPTIMIZED              = 0x0001      # use LOAD/STORE_FAST instead of _NAME
CO_NEWLOCALS              = 0x0002      # only cleared for module/exec code
CO_VARARGS                = 0x0004
CO_VARKEYWORDS            = 0x0008
CO_NESTED                 = 0x0010      # ???
CO_GENERATOR              = 0x0020
CO_NOFREE                 = 0x0040      # quick test for "no free or cell vars"
#TODO integrate CO_COROUTINE and CO_ITERABLE_COROUTINE in from_code(), to_code()
CO_COROUTINE              = 0x0080      # func created with "async def"
CO_ITERABLE_COROUTINE     = 0x0100
# The following flags are no longer used as of 3.4
CO_GENERATOR_ALLOWED      = 0x1000      # unused
CO_FUTURE_DIVISION        = 0x2000
CO_FUTURE_ABSOLUTE_IMPORT = 0x4000
CO_FUTURE_WITH_STATEMENT  = 0x8000
CO_FUTURE_PRINT_FUNCTION  = 0x10000
CO_FUTURE_UNICODE_LITERALS = 0x20000
CO_FUTURE_BARRY_AS_BDFL   = 0x40000 # Barry White. No, byte array.
CO_FUTURE_GENERATOR_STOP  = 0x80000

class Code(object):
    """

    An object that holds all the information that a Python code object holds,
    but in an easy-to-play-with representation.

    Code offers the following class methods:

    Code.from_code(code_object): analyzes a Python code object and returns
    an instance of this class that has equivalent contents.

    Code.to_code(Code_object): analyzes a Code object and returns a Python
    code object with equivalent contents.

TODO: analyze the relative benefits of having from_code() as a class method
that calls Code.__init__() with the many pieces of a code object, versus
having Code.__init__() take a whole code object and self-initializing.
(Note that from_code() does recurse into itself when handling the argument of
MAKE_FUNCTION and _CLOSURE bytecodes.)

In byteplay2, Code.__init__() takes all the pieces of a code object; in this
it kinda sorta mimics PyCodeNew() in codeobject.c, but the parallel is not
close enough to be instructive.

    The attributes of any Code object are:

    Affecting action
    ----------------

    code
        the code as a list of (opcode, argument/None) tuples. The first item
        is an opcode, or SetLineno, or a Label instance. The second item is
        the argument, if applicable, or None. code can be a CodeList instance,
        which will produce nicer output when printed.

TODO: When "can" code be a CodeList and why not always?

    freevars
        list of strings, the free vars of the code: names
        of variables used in the function but not created in it.

    args
        list of strings, the names of arguments to a function.

    varargs
        boolean: Does the function's arg list end with a '*args' argument.

    varkwargs
        boolean: Does the function's arg list end with a '**kwargs' argument

    newlocals
        boolean: Should a new local namespace be created. (True in functions,
        False for module and exec code)

TODO: should there be boolean values reflecting CO_GENERATOR,
CO_COROUTINE and CO_ITERABLE_COROUTINE?

    Not affecting action
    --------------------

    name
        string: the name of the code, from co_name.

    filename
        string: the file name of the code, from co_filename.

    firstlineno
        int: the first source line number, from co_firstlineno

    docstring
        string or None: the docstring, i.e. the first item of co_consts,
        when that is a string.

    """

    # Possibly somebody creates a Code object by calling Code() with
    # all these values. More likely, the class method from_code() below
    # is used. It takes a code object apart to find all these things
    # and creates the Code object from the parts.

    def __init__(self, code, freevars, args, varargs, varkwargs, newlocals,
                 name, filename, firstlineno, docstring):
        self.code = code
        self.freevars = freevars
        self.args = args
        self.varargs = varargs
        self.varkwargs = varkwargs
        self.newlocals = newlocals
        self.name = name
        self.filename = filename
        self.firstlineno = firstlineno
        self.docstring = docstring

    @staticmethod
    def _findlinestarts(code_object):
        """
        Find the offsets in a byte code which are the start of source lines.

        Generate pairs (offset, lineno) as described in Python/compile.c.

        This is a modified version of dis.findlinestarts. This version allows
        multiple "line starts" with the same line number. (The dis version
        conditions its yield on a test "if lineno != lastlineno".)

        FYI: code.co_lnotab is a byte array with one pair of bytes for each
        effective source line number in the bytecode. An effective line is
        one that generates code: not blank or comment lines. The first actual
        line number, typically the number of the "def" statement, is in
        code.co_firstlineno.

        An even byte of co_lnotab is the offset to the bytecode generated
        from the next effective line number. The following odd byte is an
        increment on the previous line's number to the next line's number.
        Thus co_firstlineno+co_lnotab[1] is the first effective line's
        number, and co_lnotab[0] is the number of bytes it generated.

        Note that an effective line number generates code by definition,
        hence the even byte cannot be zero; and as line numbers are
        monotonically increasing, the odd byte cannot be zero either.

        But what, the curious reader might ask, does Python do if a source
        line generates more than 255 bytes of code? In that *highly* unlikely
        case compile.c generates multiple pairs of (255,0) until it has
        accounted for all the generated code, then a final pair of
        (offset%256, lineincr).

        Oh, but what, the curious reader asks, do they do if there is a gap
        of more than 255 between effective line numbers? It is not unheard of
        to find blocks of comments larger than 255 lines (like this one?).
        Then compile.c generates pairs of (0, 255) until it has accounted for
        the line number difference and a final pair of (offset,lineincr%256).

        Uh, but...? Yes, what now, annoying reader? Well, does the following
        code handle these special cases of (255,0) and (0,255) properly?
        It handles the (0,255) case correctly, because of the "if byte_incr"
        test which skips the yield() but increments lineno. It does not handle
        the case of (255,0) correctly; it will yield false pairs (255,0).
        Fortunately that will only arise e.g. when disassembling some
        "obfuscated" code where most newlines are replaced with semicolons.

        Oh, and yes, the to_code() method does properly handle generation
        of the (255,0) and (0,255) entries correctly.

        """
        # grab the even bytes as integer byte_increments:
        byte_increments = [ord(c) for c in code_object.co_lnotab[0::2]]
        # grab the odd bytes as integer line_increments:
        line_increments = [ord(c) for c in code_object.co_lnotab[1::2]]

        lineno = code_object.co_firstlineno
        addr = 0
        for byte_incr, line_incr in zip(byte_increments, line_increments):
            if byte_incr:
                yield (addr, lineno)
                addr += byte_incr
            lineno += line_incr
        yield (addr, lineno)

    @classmethod
    def from_code(cls, code_object):
        """
        Disassemble a Python code object and make a Code object from the bits.
        """
        # get the actual bytecode string out of the code object
        co_code = code_object.co_code

        # Use dis.findlabels to locate the labeled bytecodes, that is, the
        # ones that are jump targets. (They are "labeled" in a disassembly
        # printout.) Store the list as a dict{ addr: Label object} for easy
        # lookup.

        labels = dict((addr, Label()) for addr in findlabels(co_code))

        # Make a dict{ source_line : offset } for the source lines in the code.

        linestarts = dict(cls._findlinestarts(code_object))

        # TODO: understand cellvars vs freevars vs varnames vs names
        #
        cellfree = code_object.co_cellvars + code_object.co_freevars

        # Create a CodeList object to represent the bytecode string.

        code = CodeList()
        n = len(co_code)    # number bytes in the bytecode string
        i = 0               # index over the bytecode string
        extended_arg = 0    # upper 16 bits of an extended arg

        # Iterate over the bytecode string expanding it into (Opcode,arg) tuples.

        while i < n:
            # First byte is the opcode
            op = Opcode(ord(co_code[i]))

            # If this op is a jump-target, insert (Label,) ahead of it.
            if i in labels:
                code.append((labels[i], None))

            # If this op is the first from a source line, insert
            # (SetLineno, line#) ahead of it.
            if i in linestarts:
                code.append((SetLineno, linestarts[i]))

            i += 1 # index to the argument if any

            # If this op has a code object as its argument (MAKE_FUNCTION or
            # _CLOSURE) then that code object should have been pushed on the
            # stack by a preceding LOAD_CONST. Check that. Then recursively
            # convert the argument code object into a Code and replace the
            # const with a ref to that object.

            # TODO: wouldn't this make more sense as:
            #  if op not in hasarg:... elif op in hascode: ... else...?

            if op in hascode:
                lastop, lastarg = code[-1]
                if lastop != LOAD_CONST:
                    raise ValueError(
                          "%s should be preceded by LOAD_CONST code" % op
                          )
                code[-1] = (LOAD_CONST, Code.from_code(lastarg))

            if op not in hasarg:
                # No argument, push the minimal tuple, done.
                code.append((op, None))
            else:
                # Assemble the argument value from two bytes plus an extended
                # arg when present.
                arg = ord(co_code[i]) + ord(co_code[i+1])*256 + extended_arg
                extended_arg = 0 # clear extended arg bits if any
                i += 2 # Step over the argument

                if op == opcode.EXTENDED_ARG:
                    # The EXTENDED_ARG op is just a way of storing the upper
                    # 16 bits of a 32-bit arg in the bytestream. Collect
                    # those bits but generate no code tuple.
                    extended_arg = arg << 16
                elif op in hasconst:
                    # When the argument is a constant, put the constant itself
                    # in the opcode tuple.
                    code.append((op, code_object.co_consts[arg]))
                elif op in hasname:
                    # When the argument is a name, put the name string itself
                    # in the opcode tuple.
                    code.append((op, code_object.co_names[arg]))
                elif op in hasjabs:
                    # When the argument is an absolute jump, put the label
                    # in the tuple (in place of the label list index)
                    code.append((op, labels[arg]))
                elif op in hasjrel:
                    # When the argument is a relative jump, put the label
                    # in the tuple in place of the forward offset.
                    code.append((op, labels[i + arg]))
                elif op in haslocal:
                    # When the argument is a local var, put the name string
                    # in the tuple.
                    code.append((op, code_object.co_varnames[arg]))
                elif op in hascompare:
                    # When the argument is a relation (like ">=") put that
                    # string in the tuple instead.
                    code.append((op, cmp_op[arg]))
                elif op in hasfree:
                    # TODO understand this shit
                    code.append((op, cellfree[arg]))
                else:
                    # whatever, just put the arg in the tuple
                    code.append((op, arg))

        # Store flags from the code object as booleans.
        # TODO: why do we not preserve the other names?
        # CO_OPTIMIZED, CO_VARKEYWORDS, CO_NESTED, CO_GENERATOR, CO_NOFREE, CO_COROUTINE, CO_ITERABLE_COROUTINE
        # (the latter two are 3.5 adds). Or at least, store co_flags itself
        varargs = bool(code_object.co_flags & CO_VARARGS)
        varkwargs = bool(code_object.co_flags & CO_VARKEYWORDS)
        newlocals = bool(code_object.co_flags & CO_NEWLOCALS)

        # Get the names of arguments as strings, from the varnames tuple. The
        # order of name strings is the names of regular arguments, then the
        # name of a *arg if any, then the name of a **arg if any, followed by
        # the names of locals.
        args = code_object.co_varnames[:code_object.co_argcount + varargs + varkwargs]

        # Preserve a docstring if any. If there are constants and the first
        # constant is a string, Python assumes that's a docstring.
        docstring = None
        if code_object.co_consts and isinstance(code_object.co_consts[0], basestring):
            docstring = co.co_consts[0]

        # Funnel all the collected bits through the Code.__init__() method.
        return cls(code = code,
                   freevars = co.co_freevars,
                   args = args,
                   varargs = varargs,
                   varkwargs = varkwargs,
                   newlocals = newlocals,
                   name = co.co_name,
                   filename = co.co_filename,
                   firstlineno = co.co_firstlineno,
                   docstring = docstring,
                   )

    # Define equality between Code objects the same way that codeobject.c
    # implements the equality test, by ORing the inequalities of each part.

    def __eq__(self, other):
        if (self.freevars != other.freevars or
            self.args != other.args or
            self.varargs != other.varargs or
            self.varkwargs != other.varkwargs or
            self.newlocals != other.newlocals or
            self.name != other.name or
            self.filename != other.filename or
            self.firstlineno != other.firstlineno or
            self.docstring != other.docstring or
            len(self.code) != len(other.code)
            ):
            return False

        # Compare code. For codeobject.c this is a comparison of two
        # bytestrings, but this is harder because of extra info, e.g. labels
        # should be matching, not necessarily identical.
        labelmapping = {}
        for (op1, arg1), (op2, arg2) in itertools.izip(self.code, other.code):
            if isinstance(op1, Label):
                if labelmapping.setdefault(op1, op2) is not op2:
                    return False
            else:
                if op1 != op2:
                    return False
                if op1 in hasjump:
                    if labelmapping.setdefault(arg1, arg2) is not arg2:
                        return False
                elif op1 in hasarg:
                    if arg1 != arg2:
                        return False
        return True

    # Re-create the co_flags value based in part on the booleans we pulled
    # out into the Code object (which can be modified by users of the API!)
    # and in part on the contents of the code string itself.

    # TODO: add Python 3.x flags, CO_NESTED, CO_COROUTINE, CO_ITERABLE_COROUTINE

    def _compute_flags(self):
        opcodes = set(op for op, arg in self.code if isopcode(op))

        optimized = (STORE_NAME not in opcodes and
                     LOAD_NAME not in opcodes and
                     DELETE_NAME not in opcodes)
        generator = (YIELD_VALUE in opcodes)
        nofree = not (opcodes.intersection(hasfree))

        flags = 0
        if optimized: flags |= CO_OPTIMIZED
        if self.newlocals: flags |= CO_NEWLOCALS
        if self.varargs: flags |= CO_VARARGS
        if self.varkwargs: flags |= CO_VARKEYWORDS
        if generator: flags |= CO_GENERATOR
        if nofree: flags |= CO_NOFREE
        return flags

    def _compute_stacksize(self):
        """
        Given this object's code list, compute its maximal stack usage.

        This is done by scanning the code, and computing for each opcode
        the stack state at the opcode.
        """

        code = self.code

        # A mapping from labels to their positions in the code list

        label_pos = dict( (op, pos)
                          for pos, (op, arg) in enumerate(code)
                          if isinstance(op, Label)
                        )

        # sf_targets are the targets of SETUP_FINALLY opcodes. They are recorded
        # because they have special stack behaviour. If an exception was raised
        # in the block pushed by a SETUP_FINALLY opcode, the block is popped
        # and 3 objects are pushed. On return or continue, the block is popped
        # and 2 objects are pushed. If nothing happened, the block is popped by
        # a POP_BLOCK opcode and 1 object is pushed by a (LOAD_CONST, None)
        # operation.
        #
        # Our solution is to record the stack state of SETUP_FINALLY targets
        # as having 3 objects pushed, which is the maximum. However, to make
        # stack recording consistent, the get_next_stacks function will always
        # yield the stack state of the target as if 1 object was pushed, but
        # this will be corrected in the actual stack recording.

        sf_targets = set( label_pos[arg]
                          for op, arg in code
                          if op == SETUP_FINALLY
                        )

        # What we compute - for each opcode, its stack state, as an n-tuple.
        # n is the number of blocks pushed. For each block, we record the number
        # of objects pushed.
        stacks = [None] * len(code)

        def get_next_stacks(pos, curstack):
            """
            Get a code position and the stack state before the operation
            was done, and yield pairs (pos, curstack) for the next positions
            to be explored - those are the positions to which you can get
            from the given (pos, curstack).

            If the given position was already explored, nothing will be yielded.
            """
            op, arg = code[pos]

            if isinstance(op, Label):
                # We should check if we already reached a node only if it is
                # a label.

                #TODO: is the above original comment a TODO or just a remark?
                #and what does it mean?

                if pos in sf_targets:
                    # Adjust a SETUP_FINALLY from 1 to 3 stack entries.
                    # TODO: is there a colon missing in the following???
                    curstack = curstack[:-1] + (curstack[-1] + 2,)

                if stacks[pos] is None:
                    stacks[pos] = curstack
                else:
                    if stacks[pos] != curstack:
                        raise ValueError("Inconsistent code")
                    return

            def newstack(n):
                # Return a new stack, modified by adding n elements to the last
                # block
                if curstack[-1] + n < 0:
                    raise ValueError("Popped a non-existing element")
                return curstack[:-1] + (curstack[-1]+n,)

            if not isopcode(op):
                # label or SetLineno - just continue to next line
                yield pos+1, curstack

            elif op in (STOP_CODE, RETURN_VALUE, RAISE_VARARGS):
                # No place in particular to continue to
                pass

            #elif op == MAKE_CLOSURE and python_version == '2.4':
                ## This is only relevant in Python 2.4 - in Python 2.5 the stack
                ## effect of MAKE_CLOSURE can be calculated from the arg.
                ## In Python 2.4, it depends on the number of freevars of TOS,
                ## which should be a code object.
                #if pos == 0:
                    #raise ValueError("MAKE_CLOSURE can't be the first opcode")
                #lastop, lastarg = code[pos-1]
                #if lastop != LOAD_CONST:
                    #raise ValueError( "MAKE_CLOSURE should come after a LOAD_CONST op")
                #try:
                    #nextrapops = len(lastarg.freevars)
                #except AttributeError:
                    #try:
                        #nextrapops = len(lastarg.co_freevars)
                    #except AttributeError:
                        #raise ValueError("MAKE_CLOSURE preceding const should be a code or a Code object")

                #yield pos+1, newstack(-arg-nextrapops)

            elif op not in hasflow:
                # Simple change of stack
                pop, push = getse(op, arg)
                yield pos+1, newstack(push - pop)

            elif op in (JUMP_FORWARD, JUMP_ABSOLUTE):
                # One possibility for a jump
                yield label_pos[arg], curstack

            #elif python_version < '2.7' and op in (JUMP_IF_FALSE, JUMP_IF_TRUE):
                ## Two possibilities for a jump
                #yield label_pos[arg], curstack
                #yield pos+1, curstack

            # elif python_version >= '2.7' and op in (POP_JUMP_IF_FALSE, POP_JUMP_IF_TRUE):
            elif op in (POP_JUMP_IF_FALSE, POP_JUMP_IF_TRUE):
                # Two possibilities for a jump
                yield label_pos[arg], newstack(-1)
                yield pos+1, newstack(-1)

            # elif python_version >= '2.7' and op in (JUMP_IF_TRUE_OR_POP, JUMP_IF_FALSE_OR_POP):
            elif op in (JUMP_IF_TRUE_OR_POP, JUMP_IF_FALSE_OR_POP):
                # Two possibilities for a jump
                yield label_pos[arg], curstack
                yield pos+1, newstack(-1)

            elif op == FOR_ITER:
                # FOR_ITER pushes next(TOS) on success, and pops TOS and jumps
                # on failure
                yield label_pos[arg], newstack(-1)
                yield pos+1, newstack(1)

            elif op == BREAK_LOOP:
                # BREAK_LOOP jumps to a place specified on block creation, so
                # it is ignored here
                pass

            elif op == CONTINUE_LOOP:
                # CONTINUE_LOOP jumps to the beginning of a loop which should
                # already have been discovered, but we verify anyway.
                # It pops a block.
                #if python_version == '2.6':
                  #pos, stack = label_pos[arg], curstack[:-1]
                  #if stacks[pos] != stack: #this could be a loop with a 'with' inside
                    #yield pos, stack[:-1] + (stack[-1]-1,)
                  #else:
                    #yield pos, stack
                #else:
                  #yield label_pos[arg], curstack[:-1]
                yield label_pos[arg], curstack[:-1]

            elif op == SETUP_LOOP:
                # We continue with a new block.
                # On break, we jump to the label and return to current stack
                # state.
                yield label_pos[arg], curstack
                yield pos+1, curstack + (0,)

            elif op == SETUP_EXCEPT:
                # We continue with a new block.
                # On exception, we jump to the label with 3 extra objects on
                # stack
                yield label_pos[arg], newstack(3)
                yield pos+1, curstack + (0,)

            elif op == SETUP_FINALLY:
                # We continue with a new block.
                # On exception, we jump to the label with 3 extra objects on
                # stack, but to keep stack recording consistent, we behave as
                # if we add only 1 object. Extra 2 will be added to the actual
                # recording.
                yield label_pos[arg], newstack(1)
                yield pos+1, curstack + (0,)

            elif python_version == '2.7' and op == SETUP_WITH:
                yield label_pos[arg], curstack
                yield pos+1, newstack(-1) + (1,)

            elif op == POP_BLOCK:
                # Just pop the block
                yield pos+1, curstack[:-1]

            elif op == END_FINALLY:
                # Since stack recording of SETUP_FINALLY targets is of 3 pushed
                # objects (as when an exception is raised), we pop 3 objects.
                yield pos+1, newstack(-3)

            elif op == WITH_CLEANUP:
                # Since WITH_CLEANUP is always found after SETUP_FINALLY
                # targets, and the stack recording is that of a raised
                # exception, we can simply pop 1 object and let END_FINALLY
                # pop the remaining 3.
                if python_version == '2.7':
                    yield pos+1, newstack(2)
                else:
                    yield pos+1, newstack(-1)

            else:
                assert False, "Unhandled opcode: %r" % op


        # Now comes the calculation: open_positions holds positions which are
        # yet to be explored. In each step we take one open position, and
        # explore it by adding the positions to which you can get from it, to
        # open_positions. On the way, we update maxsize.
        # open_positions is a list of tuples: (pos, stack state)
        maxsize = 0
        open_positions = [(0, (0,))]
        while open_positions:
            pos, curstack = open_positions.pop()
            maxsize = max(maxsize, sum(curstack))
            open_positions.extend(get_next_stacks(pos, curstack))

        return maxsize

    def to_code(self):
        """
        Assemble a Python code object from a Code object.
        """
        co_argcount = len(self.args) - self.varargs - self.varkwargs
        co_stacksize = self._compute_stacksize()
        co_flags = self._compute_flags()

        co_consts = [self.docstring]
        co_names = []
        co_varnames = list(self.args)

        co_freevars = tuple(self.freevars)

        # We find all cellvars beforehand, for two reasons:
        # 1. We need the number of them to construct the numeric argument
        #    for ops in "hasfree".
        # 2. We need to put arguments which are cell vars in the beginning
        #    of co_cellvars
        cellvars = set( arg for op, arg in self.code
                        if isopcode(op)
                        and op in hasfree
                        and arg not in co_freevars
                    )
        co_cellvars = [x for x in self.args if x in cellvars]

        def index(seq, item, eq=operator.eq, can_append=True):
            """
            Find the index of item in a sequence and return it.
            If it is not found in the sequence, and can_append is True,
            it is appended to the sequence.

            eq is the equality operator to use.
            """
            for i, x in enumerate(seq):
                if eq(x, item):
                    return i
            else:
                if can_append:
                    seq.append(item)
                    return len(seq) - 1
                else:
                    raise IndexError("Item not found")

        # List of tuples (pos, label) to be filled later
        jumps = []
        # A mapping from a label to its position
        label_pos = {}
        # Last SetLineno
        lastlineno = self.firstlineno
        lastlinepos = 0

        co_code = array('B')
        co_lnotab = array('B')
        for i, (op, arg) in enumerate(self.code):
            if isinstance(op, Label):
                label_pos[op] = len(co_code)

            elif op is SetLineno:
                incr_lineno = arg - lastlineno
                incr_pos = len(co_code) - lastlinepos
                lastlineno = arg
                lastlinepos = len(co_code)

                # See pedantic comments about the encoding of co_lnotab and
                # values over 255 in the prolog to from_code().

                if incr_lineno == 0 and incr_pos == 0:
                    co_lnotab.append(0)
                    co_lnotab.append(0)
                else:
                    while incr_pos > 255:
                        co_lnotab.append(255)
                        co_lnotab.append(0)
                        incr_pos -= 255
                    while incr_lineno > 255:
                        co_lnotab.append(incr_pos)
                        co_lnotab.append(255)
                        incr_pos = 0
                        incr_lineno -= 255
                    if incr_pos or incr_lineno:
                        co_lnotab.append(incr_pos)
                        co_lnotab.append(incr_lineno)

            elif op == opcode.EXTENDED_ARG:
                raise ValueError("EXTENDED_ARG not supported in Code objects")

            elif not op in hasarg:
                co_code.append(op)

            else:
                if op in hasconst:
                    if isinstance(arg, Code) and i < len(self.code)-1 and \
                       self.code[i+1][0] in hascode:
                        arg = arg.to_code()
                    arg = index(co_consts, arg, operator.is_)
                elif op in hasname:
                    arg = index(co_names, arg)
                elif op in hasjump:
                    # arg will be filled later
                    jumps.append((len(co_code), arg))
                    arg = 0
                elif op in haslocal:
                    arg = index(co_varnames, arg)
                elif op in hascompare:
                    arg = index(cmp_op, arg, can_append=False)
                elif op in hasfree:
                    try:
                        arg = index(co_freevars, arg, can_append=False) \
                              + len(cellvars)
                    except IndexError:
                        arg = index(co_cellvars, arg)
                else:
                    # arg is ok
                    pass

                if arg > 0xFFFF:
                    co_code.append(opcode.EXTENDED_ARG)
                    co_code.append((arg >> 16) & 0xFF)
                    co_code.append((arg >> 24) & 0xFF)
                co_code.append(op)
                co_code.append(arg & 0xFF)
                co_code.append((arg >> 8) & 0xFF)

        for pos, label in jumps:
            jump = label_pos[label]
            if co_code[pos] in hasjrel:
                jump -= pos+3
            if jump > 0xFFFF:
                raise NotImplementedError("Extended jumps not implemented")
            co_code[pos+1] = jump & 0xFF
            co_code[pos+2] = (jump >> 8) & 0xFF

        # TODO: following use of .tostring is probably an error in Python 3?
        co_code = co_code.tostring()
        co_lnotab = co_lnotab.tostring()

        co_consts = tuple(co_consts)
        co_names = tuple(co_names)
        co_varnames = tuple(co_varnames)
        co_nlocals = len(co_varnames)
        co_cellvars = tuple(co_cellvars)

        return types.CodeType(co_argcount, co_nlocals, co_stacksize, co_flags,
                              co_code, co_consts, co_names, co_varnames,
                              self.filename, self.name, self.firstlineno, co_lnotab,
                              co_freevars, co_cellvars)


# END OF Byteplay external API. Following are for test only.

def recompile(filename):
    """
    Given a (presumably) Python source file filename, create a filename.pyc
    file by disassembling filename and assembling it again.

    Insert code at the top of the reassembled code that prints \"reassembled
    'filename.py' imported\" to stderr when filename.pyc is executed.
    """
    # Much of the code here was based on the compile.py module.
    import os
    import imp
    import marshal
    import struct

    # Open the source file. Not checking for .py suffix, just assuming it is
    # Python. If it isn't Python, there should be a syntax error later.
    #
    # Default encoding for Python source is UTF-8; if it isn't that or ASCII
    # there will be surrogate chars that should cause a syntax error later.

    f = open( filename, mode='r', encoding='UTF-8', errors='surrogateescape' )
    codestring = f.read()

    # Get the modification timestamp of the input file. Using os.stat instead
    # of os.fstat as they are equivalent in Py3.
    #
    # Not sure why the original has a guard against an Attribute error;
    # os.stat, fileobject.fileno and stat_object.st_mtime all are documented.
    #
    # Replace long() casts with int() casts for Py3.

    try:
        timestamp = os.stat(f.fileno()).st_mtime
    except AttributeError:
        timestamp = os.stat(filename).st_mtime
    timestamp = int( timestamp )

    f.close()

    # The following is removed because as of 3.2, compile() no longer
    # requires a terminal newline.
    #if codestring and codestring[-1] != '\n':
        #codestring = codestring + '\n'

    # Compile the source producing a code object. If it isn't valid
    # Python 3, there should be a syntax error, which we diagnose.

    try:
        codeobject = compile(codestring, filename, 'exec')
    except SyntaxError as E :
        # Document the syntax error.
        msg = "Skipping '{0}' - syntax error at line {1} col {2}".format(
            E.filename, E.lineno, E.offset )
        print( msg, file=sys.stderr )
        return

    # Apply BytePlay magic to make a code list to manipulate

    cod = Code.from_code(codeobject)

    # Modify the cod list to display a message when it runs.
    # One supposes this message is checked by "make test"?

    message = "reassembled %r imported.\n" % filename

    # Insert code tuples meaning __import__('sys').stderr.write(message)

    cod.code[:0] = [
        (LOAD_GLOBAL, '__import__'),
        (LOAD_CONST, 'sys'),
        (CALL_FUNCTION, 1),
        (LOAD_ATTR, 'stderr'),
        (LOAD_ATTR, 'write'),
        (LOAD_CONST, message),
        (CALL_FUNCTION, 1),
        (POP_TOP, None),
        ]

    # Reassemble the code list to a Python code object.

    codeobject2 = cod.to_code()

    # Write the .pyc file. Note this writes filename+c which yields
    # "name.pyc" iff the input is name.py. But we didn't check for a .py
    # suffix here. So if we get valid (or null) Python source in "name.txt"
    # this creates "name.txtc".

    fc = open(filename+'c', 'w+b')
    fc.write('\0\0\0\0')
    fc.write( struct.pack( '<l', timestamp ) )
    marshal.dump(codeobject2, fc)
    fc.flush()
    fc.seek(0, 0)
    # TODO convert to importlib.util.MAGIC_NUMBER
    fc.write( imp.get_magic() )
    fc.close()

def recompile_all(path):
    """
    If path is a file, recompile it. If path is a directory, find all .py
    files in path and recompile them.
    """
    import os
    if os.path.isdir( path ):
        for root, dirs, files in os.walk( path ):
            for name in files:
                if name.endswith( '.py' ) :
                    filename = os.path.abspath( os.path.join( root, name ) )
                    print( filename, file=sys.stderr )
                    recompile( filename )
    else:
        filename = os.path.abspath(path)
        recompile(filename)

def main():
    '''
    Execute byteplay as a command on the command line.

    Expects one argument which is a path to a folder of python code, or may
    be a path to a single .py file.

    The purpose of this is to be able to test that
    X==assemble(disassemble(X)) for all X.py in the directory.

    TODO: Well, actually not, because recompile() actually adds code.
    That's probably not a good idea, or at least, should be optional?
    '''
    import os
    if len( sys.argv ) == 2 and os.path.exists( sys.argv[ 1 ] ) :
        recompile_all(sys.argv[1])
    else :
        blurb = """\
Usage: %s path-to-dir or path-to-file.py

Search recursively for *.py in the given directory, disassemble and assemble
each, adding a note when each file is imported.

Use it to test byteplay like this:
> byteplay.py Lib
> make test

Tip: before doing this, check to see which tests fail even without reassembling.
"""
        print( blurb.format( sys.argv[0] ) )

if __name__ == '__main__':
    main()
