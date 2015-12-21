# byteplay

* Originally created by Noah Raph
* Original code archived and frozen at http://code.google.com/p/byteplay
* This Repository automatically exported from code.google.com/p/byteplay

## What it is

For a full explanation with code examples, see https://pypi.python.org/pypi/byteplay/0.2.

This summary is extracted from the above pypi page:

byteplay is a module which lets you easily play with Python bytecode.
I (Noah Raph) wrote it because I needed to manipulate Python bytecode...

The basic idea is simple: define a new type, named Code,
which is equivalent to Python code objects,
but, unlike Python code objects, is easy to play with.
“Equivalent” means that every Python code object can be converted to a
Code object and vice-versa
without losing any important information on the way.

If you are interested in changing the behaviour of functions,
or in assembling functions on your own, you may find byteplay useful.
You may also find it useful if you are interested in how Python’s bytecode actually works;
byteplay lets you easily play with existing bytecode and see what happens.

## More info...

If you do not know enough about Python code objects and bytecode,
you could do worse than audit Philip Guo's
lectures on youtube
(https://www.youtube.com/playlist?list=PLzV58Zm8FuBL6OAv1Yu6AwXZrnsFbbR0S).
However, it is currently based on the code of Python2.7,
and there are significant changes in Python 3.
Still, it does walk you into the modules of CPython you need to read
in order to understand code and function objects.

Python's own documentation is quite informative, in particular in the
Python source distribution, the files Doc/library/dis.rst and
Doc/library/inspect.rst (and the dis.py and inspect.py modules 
themselves) explain a lot.

See also the Byterun project (https://github.com/nedbat/byterun),
which is a python bytecode executor written in Python.

For a different approach to building bytecode, see the Bytecode Assembler
(https://pypi.python.org/pypi/BytecodeAssembler).

For a different approach to tinkering with the contents of Python code,
see the ASTRoid module (https://pypi.python.org/pypi/astroid/1.4.2).
Unfortunately ASTroid is not documented at all.

## Why this fork?

I (tallforasmurf) would like to play with byteplay on Python 3,
which the original does not support.
I've made this fork (by export from code.google.com)
to investigate the possibility of converting it to Python 3.

The file byteplay.py is the original code by Noah.
It supports Python 2.7 and before.

The file byteplay3.py is my edited version for Python 3.
**At this time byteplay3 is a work in progress**.

When/if byteplay works with Python3,
then Ryan Kelly's Promise package (https://github.com/rfk/promise/)
which is based on byteplay,
could also be brought to Python 3, and possibly extended.


