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
(https://pypi.python.org/pypi/BytecodeAssembler) (but it only supports
through 2.7).

For a different approach to tinkering with the contents of Python code,
see the ASTRoid module (https://pypi.python.org/pypi/astroid/1.4.2).
Unfortunately ASTroid is not documented at all.

## Changes from the original...

I (tallforasmurf) am making the following changes in the API of
byteplay3 as compared to the original.

1. Only Python 3.x supported.

2. Class `Opcode.__repr__()` has different output than `Opcode.__str__()`.
   Previously they were identical; now `__repr__()` returns a string that
   could reproduce the Opcode object.

3. `CodeList.__str__()` result is now a list of strings.
   Originally it returned a single big string of the disassembled bytecode
   sequence; now it is a list of lines. The `printcodelist()` method works
   as before to print a disassembly to a file or stdout.

4. Function `getse(Opcode, arg) ==> (pop_count,push_count)` is removed.
   It is at least partially
   replaced by `opcode.stack_effect(opcode, arg) ==> net_stack_change_int`,
   which is passed in `__all__`.
   The reasons are, one, the latter is coded in C; two, it is
   maintained as part of CPython; and three, this removes 200 lines
   of obscure and tricky-to-maintain code from this module.

   Note that byteplay contained only one use of `getse()` and its output tuple
   was immedately reduced to a single int as `push-pop`, in other
   words, to the single int value returned by `stack_effect()`.
   If somebody needs the (pop,push) tuple result, you can get the original
   from BytecodeAssembler linked above, and update it to Python 3.



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


