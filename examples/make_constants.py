'''
    make_constants, a simple code optimizer

The decorator @make_constants causes the decorated function to be changed
in the following two ways.

Where it contains a LOAD_GLOBAL bytecode, the current value of the named
global is added to the functions' list of constants, and the bytecode is
changed to LOAD_CONST. This saves a name lookup in the global environment at
execution.

Second, if the code now contains any of the sequences

  LOAD_CONST LOAD_CONST* BUILD_TUPLE n
  LOAD_CONST LOAD_CONST* BUILD_LIST n
  LOAD_CONST LOAD_CONST* BUILD_SET n

(the LOAD_CONST's might well result from the first phase) the most recent
sequence of n constant values is made into a tuple, list or set which is
added to the constant list, and the n LOAD_CONST bytecodes are reduced to a
single LOAD_CONST of the folded tuple, list or set.

The inspiration for this code was a recipe by Raymond Hettinger in the Python
Cookbook, (aspn.activestate.com/ASPN/Cookbook/Python/Recipe/277940).
It was modified by Noam Raphael to demonstrate using the byteplay module and
distributed with byteplay. This version is further modified to work with
Python 3 and byteplay3, and a ton of gratuitous comments.

Arguments to @make_constants are:

    builtin_only = False
        if True, only global references to names in module builtins
        are converted. When False as usual, names in the function's
        dict of global names are also converted.

    stoplist = []
        a list (or set) of names not to be converted, perhaps because
        although they appear in the function's global names dict, their
        values are not really static.

    verbose = False
        when true, conversions are printed to stdout.

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
__version__ = "3.5.0"
__author__  = "Raymond Hettinger (original concept); Noam Yorav-Raphael (byteplay version); David Cortesi (byteplay3)"
__copyright__ = "Copyright (C) 2006-2010 Noam Yorav-Raphael; this version (C) 2016 David Cortesi"
__maintainer__ = "David Cortesi"
__email__ = "davecortesi@gmail.com"


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# The __all__ global establishes the complete API of the module on import.
#

__all__ = ['_make_constants', 'bind_all', 'make_constants' ]

from byteplay3 import *
import types
import builtins

def _func_copy(f, newcode) :
    '''
    Return a copy of function f with a different __code__
    Because I can't find proper documentation on the
    correct signature of the types.FunctionType() constructor,
    I pass the minimum arguments then set the important
    dunder-values by direct assignment.

    Note you cannot assign __closure__, it is a "read-only attribute".
    Ergo, you should not apply _make_constants() to a function that
    has a closure!
    '''
    newf = types.FunctionType( newcode, f.__globals__ )
    newf.__annotations__ = f.__annotations__
    # newf.__closure__ = f.__closure__
    newf.__defaults__ = f.__defaults__
    newf.__doc__ = f.__doc__
    newf.__name__ = f.__name__
    newf.__kwdefaults__ = f.__kwdefaults__
    newf.__qualname__ = f.__qualname__
    return newf

# This function implements a decorator; as such it takes a function
# object as its first argument and returns a replacement for it.

def _make_constants(f, builtin_only=False, stoplist=[], verbose=False):
    try:
        co = f.__code__
    except AttributeError:
        # Apparently f is not a CPython function...
        return f # ..return it unchanged
    if verbose :
        print( 'make_constants on', f.__name__ )

    # Convert the Python code object to a byteplay3 Code object.
    co = Code.from_code(co)

    # Get the names and values of all builtin functions as a dict
    # that we can modify.
    import builtins
    candidates = vars( builtins ).copy()

    # Make sure the (probably empty) don't-do list is a set
    stop_set = set( stoplist )

    if not builtin_only :
        # Allowed to constant-ize the function's globals. Add all their names
        # and values to the candidates
        candidates.update( f.__globals__ )
    else :
        # Not doing func globals: add them to the stop set
        stop_set |= set( f.__globals__.keys() )

    # Pass One: scan the list of instructions looking for (LOAD_GLOBAL,name)
    # where name is a candidate. Replace the instruction with a LOAD_CONST of
    # the name's current value.

    for i, (op, arg) in enumerate(co.code):
        if op == LOAD_GLOBAL:
            name = arg
            if name in candidates and name not in stop_set:
                value = candidates[name]
                co.code[i] = (LOAD_CONST, value)
                if verbose:
                    print( name, '-->', value )

    # Pass Two: again scan the list of instructions looking for the sequence
    # LOAD_CONST, LOAD_CONST,... BUILD_TUPLE. Create an actual tuple of the
    # referenced constant values, and replace the sequence with a single
    # LOAD_CONST.

    # We will build up a copy of the existing bytecode sequence in
    # newcode, possibly modifying it as we go.
    newcode = []

    constcount = 0 # number of sequential LOAD_CONST's at the end of newcode.
    SENTINEL = [] # An object that won't appear anywhere else

    # The following loop iterates once per (Opcode, arg) in the code.

    for op, arg in co.code:
        newconst = SENTINEL
        if op == LOAD_CONST and type(arg) != type(co) :
            # count the n'th of a sequence of LOAD_CONSTs (but
            # do not handle a LOAD_CONST of an embedded Code object,
            # such as occurs with a lambda or internal def)
            constcount += 1

        elif op == BUILD_TUPLE and arg and constcount >= arg:

            # BUILD_TUPLE expects to pop "arg" values from the stack, and
            # we have seen at least that many const's pushed. So we
            # can fold those constants into a new tuple/list/set.
            #
            # The values to fold have been saved as the "arg" most recent
            # (op,value) pairs in newcode. The values are collected in the
            # order stacked, so when the user writes (1,2) she gets (1,2).

            newconst = tuple( x[1] for x in newcode[-arg:] )

            # At this point the last "arg" tuples in newcode are the
            # LOAD_CONSTs (the current BUILD_TUPLE has not been added). Clear
            # only the used opcodes from newcode and from the count. This
            # allows for an expression like ( 1, (2,3) ) implemented as
            # LOAD_CONST, LOAD_CONST, LOAD_CONST, BUILD_TUPLE 2, BUILD_TUPLE 2.

            del newcode[-arg:]
            constcount -= arg

        else:
            # Not a LOAD_CONST nor BUILD_TUPLE with a nonzero arg,
            # so reset the count of sequential LOAD_CONST opcodes
            # at the end of newcode. Start looking for a new sequence.
            constcount = 0

        if newconst is not SENTINEL:
            # We are processing a BUILD_TUPLE following LOAD_CONST's.
            # newconst has the composite tuple value and the old LOAD_CONST's
            # have been deleted.

            newcode.append((LOAD_CONST, newconst))

            # So that is a LOAD_CONST so count it.
            constcount += 1
            if verbose:
                print( "new folded constant:", newconst )

        else:
            # Not processing a BUILD_TUPLE so just save this opcode,
            # whatever it was.
            newcode.append((op, arg))

    # We have copied and possibly modified the code; put it back in the
    # code object.

    co.code = newcode

    # Return a new function object just like the input function object, but
    # with new bytecode.
    newfun = _func_copy( f, co.to_code() )
    return newfun

_make_constants = _make_constants(_make_constants) # optimize thyself!

def bind_all(mc, builtin_only=False, stoplist=[],  verbose=False):
    """Recursively apply constant binding to functions in a module or class.

    Use as the last line of the module (after everything is defined, but
    before test code).  In modules that need modifiable globals, set
    builtin_only to True.

    """
    import types
    try:
        d = vars(mc)
    except TypeError:
        return
    for k, v in d.items():
        if isinstance( v, types.FunctionType ) :
            if verbose :
                print( 'make_constants(', v.__name__, ')' )
            newv = _make_constants(v, builtin_only, stoplist,  verbose)
            setattr(mc, k, newv)
        elif type(v) in ( type, types.ModuleType ):
            bind_all(v, builtin_only, stoplist, verbose)

@_make_constants
def make_constants(builtin_only=False, stoplist=[], verbose=False):
    """
    Return a decorator for optimizing global references.
    Verify that the first argument is a function.
    """
    if type(builtin_only) == type(make_constants):
        raise ValueError("The make_constants decorator must have arguments.")
    return lambda f: _make_constants(f, builtin_only, stoplist, verbose)

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Here endeth the useful parts of module make_constants. Following executes
# only when run as a program.
#

#import random
#@make_constants(verbose=True)
#def sample(population, k):
    #"Choose k unique random elements from a population sequence."
    #if not isinstance(population, (list, tuple, str)):
        #raise TypeError('Cannot handle type', type(population))
    #n = len(population)
    #if not 0 <= k <= n:
        #raise ValueError( "sample larger than population" )
    #result = [None] * k
    #pool = list(population)
    #for i in range(k):         # invariant:  non-selected at [0,n-i)
        #j = int(random.random() * (n-i))
        #result[i] = pool[j]
        #pool[j] = pool[n-i-1]   # move non-selected item into vacancy
    #return result

#""" Output from the example call:

#list --> <class 'list'>
#tuple --> <class 'tuple'>
#str --> <class 'str'>
#TypeError --> <class 'TypeError'>
#type --> <class 'type'>
#len --> <built-in function len>
#ValueError --> <class 'ValueError'>
#list --> <class 'list'>
#int --> <class 'int'>
#random --> <module 'random' from '/Library/Frameworks/Python.framework/Versions/3.?/lib/python3.?/random.py'>
#new folded constant: (<class 'str'>, <class 'tuple'>, <class 'list'>)
#"""
#GLOBALX = 1
#GLOBALY = 2
#GLOBALZ = 3
#def test_builds():
    #t = ( GLOBALX, GLOBALY, GLOBALZ )
    #q = ( GLOBALX, (GLOBALY, GLOBALZ), (GLOBALX, GLOBALZ) )
    #return q[1][1]
#assert 3 == test_builds()
#class test_class(object):
    #class_const = 99
    #def __init__(self):
        #self.meth_t()
    #def meth_t(self):
        #self.t = (GLOBALX,GLOBALY)
        #self.l = [GLOBALZ,GLOBALX]
    #def meth_z(self):
        #self.t = (test_class.class_const, GLOBALX)
    #@classmethod
    #def cmeth(cls):
        #x = (GLOBALY,cls.class_const)

#bind_all( test_class, verbose=True )
#@make_constants(verbose=True)
#def test_nulls():
    #nullist = []
    #nulltup = ()
    #bubbles = ( (), [], [ (), () ] )
