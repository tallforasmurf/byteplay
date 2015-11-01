# byteplay

* Originally created by Noah Raph
* Original code archived and frozen at http://code.google.com/p/byteplay
* This Repository automatically exported from code.google.com/p/byteplay

## What it is

For a full explanation with code examples, see https://pypi.python.org/pypi/byteplay/0.2.

This is a quick summary extracted from the pypi page:

byteplay is a module which lets you easily play with Python bytecode.
I (Noah) wrote it because I needed to manipulate Python bytecode...
The basic idea is simple: define a new type, named Code, which is equivalent to Python code objects,
but, unlike Python code objects, is easy to play with.
“Equivalent” means that every Python code object can be converted to a Code object and vice-versa
without losing any important information on the way.
If you are interested in changing the behaviour of functions,
or in assembling functions on your own, you may find byteplay useful.
You may also find it useful if you are interested in how Python’s bytecode actually works;
byteplay lets you easily play with existing bytecode and see what happens.

## Why this fork?

I (tallforasmurf) would like to use it on Python 3.
I've made this fork (by export from code.google.com)
to investigate the possibility of converting it to Python 3.

When/if it works with Python3, then Ryan Kelly's Promise package (https://github.com/rfk/promise/)
which is based on byteplay, could also be brought to Python 3, and possibly extended.


