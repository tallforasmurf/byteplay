'''
                        byteplay3.py

byteplay is a module supporting the disassembly, modification, and re-assembly
of Python bytecode objects.

Expected use:
    import byteplay3 as bp
    myfunc_code = bp.Code( myfunc.__code__ )
    # manipulate myfunc_code using bp. members...
    myfunc.__code__ = myfunc_code.to_code()

            API CHANGES vs. byteplay 2 (original)

1. Only Python 3.x supported, cannot use under Python 2.

2. Opcode.__repr__() has different output than Opcode.__str__()

3. CodeList.__str__() value is a list of strings, not a single string
   (but printcodelist() works as before).

4. Function getse(Opcode, arg) ==>(pop_count,push_count) is removed. Partially
   replaced by opcode.stack_effect(opcode, arg) ==> int, which is passed in
   __all__. The reasons are, one, the latter is coded in C, and two, is
   maintained as part of CPython, and three, this removes 200 lines
   of obscure and tricky-to-maintain code from this module.

   Note that this module contained only one use of getse and the tuple
   (pop,push) was immedately reduced to a single int as push-pop, in other
   words, the single int value returned by stack_effect().


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
            value is the name of the opcode, e.g. "POP_TOP" for 1.

        CodeList
            An expanded form of a Python bytecode string: a list of
            (Opcode, argument) tuples. A CodeList is the .code member of
            a Code object, just as a bytestring of opcodes is the
            co_code member of a code object.

        Label
            Class of a minimal object used to mark jump targets in a
            CodeList. A tuple (Label(),None) precedes the tuple for an opcode
            that is the destination of a jump. These tuples make it easier
            to generate a disassembly of a CodeList; they are discarded
            when to_code() re-creates the code object.

    Global vars:

        cmp_op
            a tuple of the Python comparison operator names such as "<="
            and "is not"; the strings that can appear as the argument of
            the COMPARE_OP bytecode. From the standard module "opcode".

        SetLineno
            Global var holding the single object of the SetLinenoType
            class. (SetLineno, line_number) in a CodeList marks the
            beginning of code from source line_number. These tuples are
            converted into the co_lnotab array in to_code().

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

        stack_effect( opcode, arg=None )
            given an opcode number and the opcode's argument if any,
            return the stack effect of that opcode as an int, e.g.
            stack_effect( POP_TOP, None ) ==> -1

        isopcode( opcode )
            true when opcode is a Python-defined opcode and not one
            of the two convenience values Label and SetLineno.

        printcodelist( CodeList_object, to=sys.stdout )
            print a disassembly of the code in CodeList_object to the
            default output stream or a specified file object. If "to"
            file is opened in binary mode, the output is UTF-8 encoded.

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
# "from byteplay import *" imports these names, plus a bunch of names of
# opcodes, and hence "import *" is not recommended!

__all__ = ['cmp_op',
           'Code',
           'CodeList',
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
           'SetLineno',
           'stack_effect'
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

import types # used for CodeType and FunctionType

import operator # names for standard operators such as __eq__

# The opcode module is standard, distributed in lib/python3.v, but is NOT
# documented in docs.python.org/3.v/*. It says it is "shared between dis and
# other modules which operate on bytecodes". Anyway, opcode defines all
# the bytecodes and their attributes under various names.
#
# Byteplay basically plunders opcode and re-creates its exported names with
# more information or different organization, which is discussed in the
# comments below.

import opcode

# Also, pass on the stack_effect() routine (which is actually implemented
# in CPython Modules/_opcode.c) as part of our API.
#
# Reading the code of compile.c:PyCompile_OpcodeStackEffect() it handles
# every defined opcode except two: NOP and EXTENDED_ARG. NOP is possible
# as a place-holder, so handle it here. EXTENDED_ARG is not a real opcode
# and should not get queried in this way.
#
# Also the CPython code only looks at args that are ints, so if the actual
# arg is, e.g., a string (as it might be for, e.g. LOAD_FAST), pass it as
# a zero.

def stack_effect( op, arg ):
    if op == NOP :
        return 0
    passed_arg = None
    if op in hasarg and arg is not None :
        try:
            passed_arg = int( arg )
        except:
            passed_arg = 0
    if op != opcode.EXTENDED_ARG :
        return opcode.stack_effect( op, passed_arg )
    raise ValueError( 'Attempt to get stack effect of EXTENDED_ARG' )

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
# presented by module opcode. The global opname, mentioned in the Opcode
# class definition, is established just below.
#
# In byteplay 2, Opcode.__repr__ is the same as __str__. However, __repr__()
# is supposed to return a string that will recreate the object, right?
# So I am changing it so that Opcode.__str__() = the display name, but
# Opcode.__repr__() = "Opcode(n)".

class Opcode(int):
    """
    An int which represents an opcode but its str() is the opcode name,
    for example
        Opcode(1).__str__() --> 'POP_TOP'
        Opcode(1).__repr__() --> 'Opcode(1)'
        int(Opcode(1)) --> 1
    """
    def __str__( self ):
        return opname[self]
    def __repr__( self ):
        return 'Opcode(%s)' % int(self)

# opcode.opmap is a dict of { "op_name" : op_int_value }. Here we make our
# own opmap in which op_int_value is an Opcode object rather than a simple
# int. Also, leave out 'EXTENDED_ARG'/144, which is not really an opcode,
# but merely a kludge that allows Python to encode argument values >2^16
# in the opcode bytestream. See note on the CodeList class.

opmap = { name: Opcode( bytecode )
          for name, bytecode in opcode.opmap.items()
          if name != 'EXTENDED_ARG'
        }

# opname is the inverse of opmap, dict { op_int_value : "op_name" }.
# (This is quite different from opcode.opname which is only a list.)

opname = { bytecode: name for name, bytecode in opmap.items() }

# opcodes is a set of the keys of dict opname, hence of valid bytecode
# values, for quick testing.

opcodes = set( opname.keys() )

# Now force all opcode names into our global namespace, so e.g. POP_TOP is a
# global variable with value Opcode(1).
#
# The names of these globals are also added to global __all__ (defined above)
# so they are part of our API.

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
# Define the set of the opcodes that...
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

# ..have a code object for their argument

hascode = set( [ Opcode(MAKE_FUNCTION), Opcode(MAKE_CLOSURE) ] )


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#

class CodeList(list):
    """
A CodeList is an expanded version of a Python code byte-string.

The contents of a CodeList is a series of tuples (Opcode, argument) where
Opcode is an Opcode object based on the bytecode, and argument is either
None or the actual argument value of the opcode.

Argument values are typically integers, but they can be Python type at all.
For example if a function defines an inner function, one of its first opcodes
is (LOAD_CONST, <python code object>) where the constant value is an entire
code object, in effect a large byte array. The from_code() method recursively
encodes such values as nested Code objects.

In an actual bytecode string, opcode arguments are represented as indexes
into a tuple of constants. In a CodeList, the actual argument constant values
are present in the tuple, not an index.

Also in an actual bytecode string, an integer argument that does not fit in
16 bits is represented as a sequence of 1 or more EXTENDED_ARG opcodes. In
the CodeList, the extra bits are gathered into a single long int and the
EXTENDED_ARG bytecode is dropped.

The __str__() result of a CodeList is a formatted disassembly as a list of
strings, one line per bytecode. The printcodelist() function writes the
list to a file (or stdout).

Note that CodeList __init__ method exists (to set self.changed=False) but any
argument is passed on to the parent list class. Normally there is no
argument, just x=CodeList(). It might seem like a logical move to have the
__init__() take a code bytestring and build itself, but unfortunately a
bytestring is not self-interpreting; it requires use of other slots of a code
object (code.lnotab etc). So the code that constructs a CodeList is embedded
inside the from_code() method.

CodeList is a derivative of a standard list class. The only override of
normal list behavior is the __str__() function.

    """
    def __init__( self, *args ):
        super().__init__( *args )
        self.changed = False

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

    A little Python 3 problem: if the to-file is in binary mode, we need to
    encode the strings, else a TypeError will be raised. Obvious answer, test
    for 'b' in to.mode? Nope, only "real" file objects have a mode attribute.
    StringIO objects, and the variant StringIO used as default sys.stdout, do
    not have .mode.

    However, all file-like objects that support string output DO have an
    encoding attribute. (StringIO has one that is an empty string, but it
    exists.) So, if hasattr(to,'encoding'), just shove the whole string into
    it. Otherwise, encode the string utf-8 and shove that bytestring into it.
    (See? Python 3 not so hard...)

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
    def __init__(self):
        super().__init__()
        self.__str__ = self.__repr__
    def __repr__(self):
        return 'SetLineno'

SetLineno = SetLinenoType()

# Two, the Label type which represents the target of a jump. (There is no
# bytecode in a real codestring for this; it is implicit in the numeric
# arguments of "hasjump" opcodes. The class Label is also in __all__.

class Label(object):
    pass

# This boolean function allows distinguishing real opcodes in a CodeList from
# the two non-opcode types. Note there should only ever exist the one
# instance of SetLinenoType, the global SetLineno. But who knows?

def isopcode(obj):
    """
    Return whether obj is an opcode - not SetLineno or Label
    """
    return not isinstance(obj,SetLinenoType) and not isinstance(obj, Label)

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
CO_VARARGS                = 0x0004      # signature contains *arg
CO_VARKEYWORDS            = 0x0008      # signature contains **kwargs
CO_NESTED                 = 0x0010      # ???
CO_GENERATOR              = 0x0020      # func contains "yield" opcode
CO_NOFREE                 = 0x0040      # quick test for "no free or cell vars"
CO_COROUTINE              = 0x0080      # func created with "async def"
CO_ITERABLE_COROUTINE     = 0x0100      # async def func has "yield"
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

    Code offers the following class method:

    Code.from_code(code_object): analyzes a Python code object and returns
    an instance of Code class that has equivalent contents.

    The attributes of any Code object are:

    to_code()
        analyzes the contents and returns a Python code object with
        equivalent contents.

    code
        the code as CodeList; see class CodeList above.

    freevars
        list of strings, names of "free" vars of the code. Technically a "free"
        variable should be one that is used in the code but not defined in it.
        In CPython terminology it is one that is used in this code and known
        to be defined in an enclosing scope = outer function.

    args
        list of strings, the names of arguments to a function.

    varargs
        boolean: Does the function's arg list contain a '*args' argument?

    varkwargs
        boolean: Does the function's arg list end with a '**kwargs' argument?

    kwonlyargcount
        int: the count of keyword-only arguments (those that followed the
        *args in the signature of the def statement).

    newlocals
        boolean: Should a new local namespace be created? (True in functions,
        False for module and exec code)

    coflags
        int: the original co_flags value of the code object given to
        from_code(). Can be interrogated for CO_COROUTINE, CO_GENERATOR,
        CO_ITERABLE_COROUTINE, CO_OPTIMIZED. If to_code() finds that
        the code list is unchanged since from_code() built it, these
        flags are reproduced in the output.

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

    # Usually a Code object is created by the class method from_code() below.
    # However you can create one directly by supplying at least a CodeList.
    # Due to the substantial argument list, this, like the code object
    # itself, is "not for the faint of heart".

    def __init__(self,
                 code,
                 freevars = [],
                 args = [],
                 varargs = False,
                 varkwargs = False,
                 kwonlyargcount = 0,
                 newlocals = False,
                 coflags = 0x00,
                 name = '',
                 filename = '',
                 firstlineno = 1,
                 docstring = ''
                 ) :
        self.code = code
        self.freevars = freevars
        self.args = args
        self.varargs = varargs
        self.varkwargs = varkwargs
        self.kwonlyargcount = kwonlyargcount
        self.newlocals = newlocals
        self.coflags = coflags
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
        byte_increments = [c for c in code_object.co_lnotab[0::2]]
        # grab the odd bytes as integer line_increments:
        line_increments = [c for c in code_object.co_lnotab[1::2]]

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
        This is the expected way to make a Code instance. But you are welcome
        to call Code() directly if you wish.
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

        code = list()       # ordinary list receives (op,arg) tuples
        n = len(co_code)    # number bytes in the bytecode string
        i = 0               # index over the bytecode string
        extended_arg = 0    # upper 16 bits of an extended arg

        # Iterate over the bytecode string expanding it into (Opcode,arg) tuples.

        while i < n:
            # First byte is the opcode
            op = Opcode( co_code[i] )

            # If this op is a jump-target, insert (Label,) ahead of it.
            if i in labels:
                code.append((labels[i], None))

            # If this op is the first from a source line, insert
            # (SetLineno, line#) ahead of it.
            if i in linestarts:
                code.append((SetLineno, linestarts[i]))

            i += 1 # step index to the argument if any

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
                arg = co_code[i] + co_code[i+1]*256 + extended_arg
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

        # Convert the code list into a CodeList. Do this in a single step so that
        # code.changed==False.

        code = CodeList( code )

        # Store certain flags from the code object as booleans for convenient
        # reference as Code members.

        varargs = bool(code_object.co_flags & CO_VARARGS)
        varkwargs = bool(code_object.co_flags & CO_VARKEYWORDS)
        newlocals = bool(code_object.co_flags & CO_NEWLOCALS)

        # Get the names of arguments as strings, from the varnames tuple. The
        # order of name strings in co_varnames is:
        #   names of regular (positional-or-keyword) arguments
        #   names of keyword-only arguments if any
        #   name of a *vararg argument
        #   name of a **kwarg argument if any (not present if kwonlyargs > 0)
        #   names of other local variables
        # Hence the count of argument names is
        #   co_argcount + co_kwonlyargcount + varargs + varkwargs
        nargs = code_object.co_argcount + code_object.co_kwonlyargcount + varargs + varkwargs
        args = code_object.co_varnames[ : nargs ]

        # Preserve a docstring if any. If there are constants and the first
        # constant is a string, Python assumes that's a docstring.
        docstring = None
        if code_object.co_consts and isinstance(code_object.co_consts[0], str):
            docstring = code_object.co_consts[0]

        # Funnel all the collected bits through the Code.__init__() method.
        return cls( code = code,
                    freevars = code_object.co_freevars,
                    args = args,
                    varargs = varargs,
                    varkwargs = varkwargs,
                    kwonlyargcount = code_object.co_kwonlyargcount,
                    newlocals = newlocals,
                    coflags = code_object.co_flags,
                    name = code_object.co_name,
                    filename = code_object.co_filename,
                    firstlineno = code_object.co_firstlineno,
                    docstring = docstring
                    )

    # Define equality between Code objects the same way that codeobject.c
    # implements the equality test, by ORing the inequalities of each part.
    # If all attributes are equal, then test the individual tuples of the
    # two CodeList objects.

    def __eq__(self, other):
        if (self.freevars != other.freevars or
            self.args != other.args or
            self.varargs != other.varargs or
            self.varkwargs != other.varkwargs or
            self.kwonlyargcount != other.kwonlyargcount or
            self.newlocals != other.newlocals or
            self.name != other.name or
            self.filename != other.filename or
            self.firstlineno != other.firstlineno or
            self.docstring != other.docstring or
            len(self.code) != len(other.code)
            ):
            return False

        # Compare code. For codeobject.c this would be a comparison of two
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

    def _compute_flags(self):
        # take a census of the unique opcodes used.
        opcodes = set(op for op, arg in self.code if isopcode(op))

        # calculate CO_OPTIMIZED based on opcode usage.
        optimized = (STORE_NAME not in opcodes and
                     LOAD_NAME not in opcodes and
                     DELETE_NAME not in opcodes)

        # note if a yield is used.
        generator = (YIELD_VALUE in opcodes)

        # CO_NOFREE means, no opcodes that refer to "free" vars
        nofree = not (opcodes.intersection(hasfree))

        flags = 0
        if optimized: flags |= CO_OPTIMIZED
        if self.newlocals: flags |= CO_NEWLOCALS
        if self.varargs: flags |= CO_VARARGS
        if self.varkwargs: flags |= CO_VARKEYWORDS
        if generator: flags |= CO_GENERATOR
        if nofree: flags |= CO_NOFREE

        # Something we cannot calculate from opcode usage: is this a
        # coroutine? Just test the original flag value.

        if self.coflags & CO_COROUTINE :
            flags |= CO_COROUTINE
            if generator :
                flags |= CO_ITERABLE_COROUTINE

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

            elif op in ( RETURN_VALUE, RAISE_VARARGS ):
                # No place in particular to continue to
                pass

            elif op in (JUMP_FORWARD, JUMP_ABSOLUTE):
                # One possibility for a jump
                yield label_pos[arg], curstack

            elif op in (POP_JUMP_IF_FALSE, POP_JUMP_IF_TRUE):
                # Two possibilities for a jump
                yield label_pos[arg], newstack(-1)
                yield pos+1, newstack(-1)

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

            elif op == SETUP_WITH:
                yield label_pos[arg], curstack
                yield pos+1, newstack(-1) + (1,)

            elif op == POP_BLOCK:
                # Just pop the block
                yield pos+1, curstack[:-1]

            elif op == END_FINALLY or op == POP_EXCEPT:
                # Python3 has POP_EXCEPT which executes UNWIND_EXCEPT_HANDLER
                # just as END_FINALLY does, so I have added that to this branch.
                #
                # Since stack recording of SETUP_FINALLY targets is of 3 pushed
                # objects (as when an exception is raised), we pop 3 objects.
                yield pos+1, newstack(-3)

            elif op == WITH_CLEANUP:
                # Since WITH_CLEANUP is always found after SETUP_FINALLY
                # targets, and the stack recording is that of a raised
                # exception, we can simply pop 1 object and let END_FINALLY
                # pop the remaining 3.
                yield pos+1, newstack(-1)

            else:
                # nothing special, use the CPython value
                yield pos+1, newstack( stack_effect( op, arg ) )


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
        Assemble a Python code object from this Code object.
        """
        co_argcount = len(self.args) - self.varargs - self.varkwargs
        co_kwonlyargcount = self.kwonlyargcount
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

        co_code = co_code.tostring()
        co_lnotab = co_lnotab.tostring()

        co_consts = tuple(co_consts)
        co_names = tuple(co_names)
        co_varnames = tuple(co_varnames)
        co_nlocals = len(co_varnames)
        co_cellvars = tuple(co_cellvars)

        return types.CodeType(co_argcount, co_kwonlyargcount, co_nlocals, co_stacksize, co_flags,
                              co_code,
                              co_consts, co_names, co_varnames,
                              self.filename, self.name, self.firstlineno, co_lnotab,
                              co_freevars, co_cellvars)


# END OF Byteplay external API. Following are for test only.

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Given a function, take its code object to a Code object, and back again.
# Return a new function that uses the recompiled code object.

def recompile( function ) :
    test_code_object = function.__code__
    expanded_code = Code.from_code( test_code_object )
    new_function = types.FunctionType(
        code = expanded_code.to_code(),
        globals = function.__globals__,
        name = function.__name__,
        argdefs = function.__defaults__,
        closure = function.__closure__
        )
    return new_function

# Iterate through a list of tests. Each item in the list is a tuple,
# ( func [, arg1,...] ), a function followed by its zero or more
# argument values.

def test_a_list( func_list ) :

    for func_tuple in func_list:

        test_func = func_tuple[0]
        test_args = func_tuple[1:]

        try:
            result = test_func( *test_args )
        except Exception as e :
            result = e # expected exception?
        try :
            mod_func = recompile( test_func )
            try :
                mod_result = mod_func( *test_args )
            except Exception as e :
                mod_result = e
            if result != mod_result :
                print( 'test ', test_func.__name__, test_args, ' failed' )
                print( 'test result:', result )
                print( 'recompiled result:', mod_result )
            else :
                print( test_func.__name__, test_args )
        except Exception as e :
            print( 'Recompile of ',test_func.__name__, 'failed with', e )

# TODO: add more sophisticated test cases, generators, globals, closures etc.

def test_0():
    ''' minimal test case '''
    a = 2
    b = a/2
    return b

def test_1(n):
    ''' test case with a for-loop and some ifs '''
    if n > 0 :
        s = 0
        for i in range(n) :
            s += i
    else :
        s = 0
    return s

case_list = [ (test_0, ), (test_1, 5), (test_1, -1) ]

def main():
    test_a_list( case_list )

# TODO: write separate test program that imports byteplay3 and
# recompiles source files in the manner of byteplay2.

if __name__ == '__main__':
    main()
