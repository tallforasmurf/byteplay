#!/usr/bin/python

from setuptools import setup, find_packages

setup(
       name = 'byteplay3',
       author='David Cortesi, Noam Yorav-Raphael',
       author_email='davecortesi@gmail.com',
       url='https://github.com/tallforasmurf/byteplay',
       download_url='https://github.com/tallforasmurf/byteplay/archive/master.zip',
       version = "3.5.0",
       py_modules = ['byteplay3'],
       zip_safe = True,
       license='LGPL',
       description='bytecode manipulation library for Python 3',
       long_description = """byteplay lets you convert Python code objects into equivalent objects which are easy to play with, and lets you convert those objects back into Python code objects. It's useful for applying crazy transformations on Python functions, and is also useful in learning Python byte code intricacies. It currently works with Python 3.4 and up.

byteplay3 Summary
==================

For the full documentation see the "about" file located at
https://github.com/tallforasmurf/byteplay/blob/master/about.md

About byteplay
--------------

byteplay3 is a module which lets you easily play with Python bytecode.
The basic idea is simple: define a new type named Code which is equivalent
to Python code objects, but, unlike Python code objects, is easy to play
with. "Equivalent" means that every Python code object can be converted to
a Code object and vice-versa without losing any important information.
"Easy to play with" means the bytecode instructions are represented in a
way that is easy to examine and modify.

Compatibility
----------------

This module, byteplay3, is based on the original by Noam Raph, which
is still available from pypi. If you have code that used byteplay under
Python 2, you can migrate to Python3 just by changing the import line
to read "from byteplay3 import *". For minor incompatibilities, see the
"about" file linked above. Of course you will find more than minor
incompatibilities in Python 3's bytecode, which is considerably changed.

A Quick Example
---------------

Start with a silly function, convert its code to a Code object and display it::

	>>> def f(a, b):
	...   print(a, b)
	...
	>>> f(3, 5)
		3 5
	>>> from byteplay3 import *
	>>> # convert the code object of function f to a Code object
	>>> c = Code.from_code(f.__code__)
	>>> c
		<byteplay3.Code object at 0x1030da3c8>
	>>> # display the bytecode tuples in the Code object
	>>> print( c.code )
	2        1 LOAD_GLOBAL          print
			 2 LOAD_FAST            a
			 3 LOAD_FAST            b
			 4 CALL_FUNCTION        2
			 5 POP_TOP              
			 6 LOAD_CONST           None
			 7 RETURN_VALUE  
			 
Ok, now let's play! Say we want to change the function so it prints its
arguments in reverse order. To do this, we will insert a ROT_TWO opcode
after the two arguments were loaded to the stack. (That is, after
LOAD_FAST b and before CALL_FUNCTION 2.)::

    >>> c.code[4:4] = [(ROT_TWO,None)]
    
Then replace the code object in function f with a new one::

	>>> f.__code__ = c.to_code()
	>>> f(3,5)
		5 3
       """
)
