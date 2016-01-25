# byteplay3 Documentation #

## About byteplay3 ##

byteplay3 is a fork of a module written by Noam Raph
(see **History** below for details and links).
If you already have code that imports byteplay and want to 
move that code to Python 3,
you can do so by changing your import statement
`from byteplay import *` so it reads `from byteplay3 import *`.
Pretty much everything should work as before,
but you should review the **API Changes** section below.

### Important Notes and Warnings ###

**Note**: If you do not have existing code using byteplay,
and your only interest is to inspect the bytecode of functions,
be aware that with Python version 3.4,
the standard module `dis` includes a function
`dis.get_instructions(item)`
where `item` may be a function or a code object.
It returns a generator that yields a `dis.Instruction` object
for each bytecode instruction in sequence, with copious
information about that instruction.

This standard module feature basically duplicates and supercedes byteplay3
for purposes of bytecode display and study, and can be expected to be
maintained promptly and correctly with each new version.

**Caution**: The bytecodes defined by the CPython interpreter
change in almost every release.
(For example, Python 3.5 introduced new opcodes to deal with
functions defined with `async def`,
and also split the WITH\_CLEANUP opcode into two,
WITH\_CLEANUP\_START and WITH\_CLEANUP\_FINISH.)

The byteplay3 module exports as global names,
all the opcodes defined in the standard module `opcode`.
These names will automatically be the ones defined in the version of Python that is executing byteplay3.
However, byteplay3 has some code that depends on specific opcodes,
(as may your code) and it may not have been updated for the latest bytecodes.
Expect the unexpected when changing versions of Python.

**Caution**: When you use byteplay3 to modify bytecode or compose new bytecode,
your mistakes are likely to crash the CPython interpreter.
CPython assumes that any bytecode was produced in its `compile.c`
module, and trusts it implicitly.
It makes no consistency checks and does not guard against
wrong bytecode values.
The first sign that you produced invalid bytecode may be a segmentation fault in Python.

### About Python bytecode ###

You probably would not be interested in byteplay if you did not know
about bytecode, but let us have a quick refresher.

When Python processes a `def` or `lambda` statement or a `compile()` call,
it reduces the text version of the source code to a binary form that is
more efficient to process.
You know that everything in Python is an object,
so no surprise, the compilation of a defined function (or lambda) is a *function object*.
The function object has among many attributes, a *code object*.
(A `compile()` call returns a code object directly.)

A code object is how Python represents executable code.
It has a number of interesting attributes that you need to know
about in order to understand it, but its heart is
a sequence of bytes that represent instructions to a simple stack machine.
When these *bytecodes* are executed (by the CPython module `ceval.c`),
the result is to do what the function was designed to do.

(Note you can inspect the attributes of a function object or code object
easily with the `byteplay3.print_attr_values()` function.)

The purpose of byteplay3 is to make it possible to examine
and modify the sequence of bytecodes of a code object.
You might do this to understand the operation of the Python
interpreter; you might do it in order to optimize the speed
of existing code, or you might do it to generate executable
bytecode starting from some other notation.

To learn more about bytecodes, consult one of these sources:

* Ryan Kelly's short talk
  ["Bytecode: What, Why, and How to Hack it"](https://www.youtube.com/watch?v=ve7lLHtJ9l8),
  which contains a demonstration of using byteplay.
  The examples Ryan shows are very specific to Python 2
  and not very relevant to Python 3.
  However, he clearly shows the approach one could take using byteplay.

* Brett Cannon's talk on
  [how CPython compiles source to bytecode](https://www.youtube.com/watch?v=R31NRWgoIWM)

* Yanin Akniv's
  [tour of bytecode execution](http://tech.blog.aknin.name/2010/04/02/pythons-innards-introduction)
  is especially good on the contents of a code object.

* In the CPython source distro, see the files `Doc/library/dis.rst` and
  `Doc/library/inspect.rst`.
  In your installed Python, read the `opcode.py`, `dis.py` and `inspect.py` modules 
  themselves.

### The Code and CodeList classes ###

byteplay3 defines a class named Code.
A Code object is created from a Python code object,
but unlike a code object, it can easily be examined and modified.

A Python code object contains a string of bytecodes;
and a Code object contains a matching string of bytecodes
as a CodeList object.

Any Python code object can be converted to a Code object,
and the Code object converted back to a code object,
without losing any important information on the way.

### A Quick Example ###

Let's start from a quick example, to give you a taste of what byteplay does.

    >>> def f(a, b):
    ...   print(a, b)
    ...
    >>> f(3, 5)
        3 5
    >>> from byteplay3 import *
    >>> # convert code object of function f to a Code object
    >>> c = Code.from_code(f.__code__)
    >>> c
        <byteplay3.Code object at 0x1030da3c8>
    >>> # display the bytecode tuples in the Code object
    >>> for op, arg in c.code:
    ...   print(op, arg)
    ...
        SetLineno 2
        LOAD_GLOBAL print
        LOAD_FAST a
        LOAD_FAST b
        CALL_FUNCTION 2
        POP_TOP None
        LOAD_CONST None
        RETURN_VALUE None

This should be pretty clear if you are a bit familiar with bytecode.
The Code object contains all the values from a Python code object,
including the bytecode sequence.
However the bytecode sequence is converted into a list of all operations
in the form of a CodeList object.
Unlike the compact but complicated format of a bytecode string,
the CodeList contains a tuple of (opcode, arg) for each bytecode.
Not all opcodes have an argument,
so those have None as their argument value in the list.

Where an opcode takes an argument,
the actual argument value is present in the tuple.
For example, the argument of LOAD\_GLOBAL is the name `print`.
In the raw bytecode,
the argument of many opcodes is an index to a table.
For example, the argument of LOAD\_FAST in raw bytecode is an index to the table of local variable names.
In the CodeList, the actual variable name is given as the argument.
Similarly, the argument of LOAD\_CONST in raw bytecode is an index to the
`co_consts` table, which contains the actual constants.
Here, the argument is the constant itself (the constant None,
which is loaded in order to return it as the function result).

Also note the SetLineno "opcode".
It is not a Python opcode.
It is used to mark where a line in the original source code begins.
Its argument is the source code line number.
Except for that and another special opcode which we will see later,
all other opcodes are the real opcodes used by the Python interpreter.

If you want to see the code list in a form easier to read, just print it.
Python's print function uses the `__str__` value of the code list,
and the CodeList class's string value is a disassembly in the style
of the standard  module `dis.dis`.

    >>> print(c.code)
    2        1 LOAD_GLOBAL          print
             2 LOAD_FAST            a
             3 LOAD_FAST            b
             4 CALL_FUNCTION        2
             5 POP_TOP              
             6 LOAD_CONST           None
             7 RETURN_VALUE         
    

Ok, now let's play!
Say we want to change the function so it prints its arguments in reverse order.
To do this, we will insert a ROT\_TWO opcode after the two arguments were loaded to the stack.
(That is, after `LOAD_FAST b` and before `CALL_FUNCTION 2`.)

    >>> c.code[4:4] = [(ROT_TWO,None)]

Then replace the code object in function `f` with the new one.

    >>> f.__code__ = c.to_code()
    >>> f(3,5)
        5 3

### Where to get a code object ###

You make a Code object from a Python code object.
As demonstrated in the example,
the most common source of a code object is the `__code__` attribute 
of a function object.
Here are the main sources:

* The output of the `compile()` built-in function is a code object.

* Attribute `__code__` of a function object.

* Attribute `__code__` of a lambda object (which is a function).

* Functions accessed by way of the name of a class:

	+ _classname_`.`_methodname_`.__code__`, including normal methods and methods
	  with the `@staticmethod` decorator

	+ _classname_`.`_classmethod_`.__func__.__code__` for methods declared with the
	  `@classmethod` decorator

	+ _classname_`.`_propertyname_`.fget.__code__` where _propertyname_ is declared
	  with the `@property` decorator

	+ _classname_`.`_propertyname_`.fset.__code__` where the class contains
	  the `@`_propertyname_`.setter` decorator

	+ _classname_`.`_propertyname_`.fdel.__code__` where the class contains
	  the `@`_propertyname_`.deleter` decorator

* Functions accessed by way of the name of an object, an instance of a class:

	+ _objectname_`.`_methodname_`.__func__.__code__` for normal and class
	  methods accessed through an instance of the class

	+ _objectname_`.`_methodname_`.__code__` for class methods declared
	  with `@staticmethod`, accessed through an instance of the class

## Class Opcode ##

We have seen that the code list contains opcode constants such as LOAD\_FAST.
These are instances of the Opcode class.
The Opcode class is merely a subclass of `int`.
Each Opcode object is just an int such as `124`.
However it overrides the `__str__()` method to return the string representation of an opcode:

    >>> print( 124, Opcode(124) )
        124 LOAD_FAST
	>>> for i in range(10):print(i, Opcode(i) )
		0 0
		1 POP_TOP
		2 ROT_TWO
		3 ROT_THREE
		4 DUP_TOP
		5 DUP_TOP_TWO
		6 6
		7 7
		8 8
		9 NOP

The Opcode of an integer that is not defined just prints the integer,
as shown.

When you make a Code object using `Code.from_code()`,
all the opcodes in its CodeList are Opcode objects.
It is not essential to use an Opcode when updating or inserting a CodeList tuple;
an integer constant such as 124 can be used.
Opcode instances are easier to read when printed.

When byteplay3 is imported, it creates a global constant for every valid
bytecode as defined in the standard module `opcode`.
(Thus exactly and only the opcode names that are known to the version
of Python that is executing byteplay3.)
Each of these constants is an Opcode object;
for example the global constant `LOAD_FAST` is defined as `Opcode(124)`.
When you write `from byteplay3 import *` all these names are added to your namespace.

### EXTENDED\_ARG ###

A Python code object can contain the special opcode EXTENDED\_ARG.
It is basically a hack,
used because the argument value of a bytecode is limited to 16 bits.
Occasionally a bytecode needs an argument value with more bits.
In that case it is preceded by an EXTENDED\_ARG with the high-order
bits as argument.

When byteplay3 converts a code object to a Code object,
it combines the bits into a single argument value and discards the EXTENDED\_ARG.
When converting back to raw bytecode it inserts EXTENDED\_ARG codes as needed.

## The byteplay3 API ##

The following are the names exported by the byteplay3 module in its `__all__` list,
which means these are the names that you acquire using `from byteplay3 import *`.

### Opcode names and sets ###

`POP_TOP`, `ROT_TWO`, ... `BUILD_SET_UNPACK`
  All opcode constants from standard module `opcode`
  are defined as Opcode objects.

`opcodes`
  A set of all Opcode instances.

`opmap`
  A dict {opname : Opcode} mapping from an opcode name string to an Opcode instance.

`opname`
  A dict {int : opname} mapping from an opcode number (or Opcode instance) to its name string.

`cmp_op`
  A list of strings which represent comparison operators.
  In raw bytecode, the  argument of a COMPARE\_OP is an index to this list.
  In a CodeList, it is the string representing the comparison.

The following are sets of Opcodes which allow quick testing of an opcode
for its behavior.

`hasarg`
  The set of opcodes that take an argument.

`hasname`
  The set of opcodes that whose argument is a name string (of a global,
  an attribute, or other name).

`hasjrel`
  The set of opcodes whose argument is a relative jump, that is,
  an offset to be algebraically added to the byte code instruction pointer.

`hasjabs`
  The set of opcodes whose argument is an absolute jump, that is, an
  offset to be assigned to the instruction pointer.

`hasjump`
  The set of opcodes whose argument is a jump,
  simply `hasjrel+hasjabs`.

`haslocal`
  The set of opcodes that operate on local variables.

`hascompare`
  The set of opcodes whose argument is a comparison operator.
  A singleton set, the COMPARE\_OP opcode.

`hasfree`
  The set of opcodes that operate on the cell and free variable storage.
  See **About Freevars** below.

`hascode`
  The set of opcodes that expect a code object to be at the top of the stack.
  In the bytecode the Python compiler generates, they are always
  preceded by a LOAD\_CONST of the code object followed by a
  LOAD\_CONST of the function name.
  These get special treatment in the `Code.from_code()` and `Code.to_code()`
  methods, described later.

`hasflow`
  This set contains all opcodes which have a special flow behaviour.
  All other opcodes always continue to the next opcode after finished,
  unless an exception was raised.
  These opcodes may or may not.
  The set includes the `hasjump` set and others such as YIELD\_FROM.

`SetLineno`
  This singleton class is used like the Opcodes,
  but it is simply a place-holder in the CodeList to show that
  the following opcode begins the bytecode for a specific line in the source code.
  When converting back to a code object, these source line positions are
  encoded in a different part of the code object.

`Label`
  This is the class of label objects.
  Items of this class in a CodeList mark the place where some
  relative or absolute jump terminates.

`isopcode(obj)`
  Returns True when _obj_ is a real Opcode, not a SetLineno marker.
  Effectively,
  
    obj is not SetLineno and not isinstance(obj, Label)

  Note that it does not test whether _obj_ is a valid opcode.

### Utility functions ###

These functions are available for general use.

`stack_effect(Opcode, arg)`
  Yields the _net stack change_ of that Opcode and argument.
  This calls on the function of the same name in the standard `opcode` module,
  which in turn calls on an internal CPython routine in `compile.c`.

`getse(opcode, arg)`
  Returns the stack effect of an opcode, as a (pop-count, push-count) tuple.
  The stack effect is the number of items popped from the stack,
  and the number of items pushed in place of them.
  (This function has changed from byteplay2, see [API Changes](#API_Changes) below.)

`printcodelist(thing, to=sys.stdout)`
  This function displays the bytecode of any executable in the manner of the
  standard `dis.dis` function.
  The _thing_ may be a CodeList object, or a Code object,
  or it may be a Python code object or a function or lambda object.
  (To print a disassembly listing of a CodeList, just `print()` it.)

`object_attributes(thing)`
  Returns a list of the names of the attributes of _thing_
  that are not also attributes of the Python object type.
  Basically dir(thing) - dir(object).

`print_object_attributes( thing, heading=None, file=None)`
  Prints a vertical, sorted column of the names returned by
  `object_attributes(thing)`.
  If a heading string is given it is printed above the list.
  If a file object is given, output goes to that file, else to stdout.

`print_attr_values(thing, all=False, heading=None, file=None)`
  Prints a two-column list showing the attributes returned by
  `object_attributes(thing)` with their current values.
  If `all=True` all attributes are printed.
  When `all=False` only attributes with non-null values are printed.
  If `heading` is a string, it is printed above the output.
  If `heading` is an integer, a default heading line is generated like
  `== all attributes of thing-name ==`.
  Output is to the given file object or to stdout.

## The Code Class ##

### Constructor ###

The Code object represents the contents of a Python code object.
The docstring of a code object (as you can verify with `print_attr_values()`)
says, "Not for the faint of heart."
The Code object constructor takes a similar and very complex
list of arguments:

    Code( code,
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
		 )

Normally it is best to create a Code object using the class method,
`Code.from_code()` which takes a Python code object,
extracts its important features,
and constructs the Code instance.
Even if you mean to supply all or most of the bytecode for a function,
it is simpler to define a minimal function with the desired signature
and use `Code.from_code()` to build the initial Code object.

### Data Attributes ###

These are the data attributes of a Code instance.
They are read/write.
If you change them, the change will be reflected in the Python 
code object returned by `Code.to_code()`.

`code`
  This is the list of executable bytecodes.
  It is given as a list of tuples `(opcode, arg)`,
  as described earlier.
  The `opcode` value is of three types:
  
  * `SetLineno` means that a line in the source code begins.
    Its argument is the line number.

  * Labels, instances of the `Label` class.
    These are used as a way to specify a place in the code list.
    Labels can be put anywhere in the code list and cause no action by themselves.
    Opcodes that may cause a jump give the index of a (Label,None) pair
    as their destination.

  * Opcodes not in the `hasarg` set take None as their argument.
  
  * Opcodes in the `hasarg` set take arguments as follows:
    - Opcodes in `hasconst` take an actual constant.
    - Opcodes in `hasname` take a name, as a string.
    - Opcodes in `hasjump` take the index of a Label instance at a specific location in the code list.
    - Opcodes in `haslocal` take the local variable name, as a string.
    - Opcodes in `hascompare` take the string representing the comparison operator.
    - Opcodes in `hasfree` take the name of the cell or free variable, as a string.
    - The argument of the remaining opcodes is the numerical argument found in
      raw bytecode. Its meaning is opcode-specific.
 
 Note that Python avoids redundancy in bytecode by using arguments that
  are indexes into a table of unique constants or names.
  The Code object does not do this.
  If a name or constant is used multiple times,
  it appears multiple times as argument values.

`freevars`
  This is a list of strings,
  the names of variables defined in outer functions and used in this function
  or in functions defined inside it.
  The order of this list is important,
  since those variables are passed to the function in the same sequence
  as the names in the `freevars` list.
  See **About Freevars** below.
  
`args`
  The list of argument names of a function. For example::

    >>> def f(a, b, *args, **kwargs):
    ...     pass
    ...
    >>> Code.from_code(f.__code__).args
        ('a', 'b', 'args', 'kwargs')

`varargs`
  A boolean: Does the function get a variable number of positional arguments?
  In other words: does it have a ``*args`` argument?
  If ``varargs`` is True, the argument which gets that extra positional
  arguments will be the last argument or the one before the last, depending
  on whether ``varkwargs`` is True.

``varkwargs``
  A boolean: Does the function get a variable number of keyword arguments?
  In other words: does it have a ``**kwargs`` argument?
  If ``varkwargs`` is True, the argument which gets the extra keyword arguments
  will be the last argument.

`kwonlyargcount`
  An int, the number of keyword-only arguments, that is,
  arguments that appear in the function signature _after_ a `*args` argument.

    >>> def f( a, *args, q=None):
    ...     pass
    ...
    >>> Code.from_code(f.__code__).args
        ('a', 'q', 'args')
    >>> Code.from_code(f.__code__).kwonlyargcount
        1
  
``newlocals``
  A boolean: Should a new local namespace be created for this code?
  This is True for functions, False for modules and exec code.

Now come attributes with additional information about the code:

`coflags`
  An int, the binary value of the code object's `co_flags` value.
  Some of the `co_flags` bits are passed separately (`varargs`, `varkwargs`)
  but the entire flag integer is preserved, so that flags such
  as CO\_COROUTINE can be preserved without needing additional booleans.

``name``
  A string: The name of the code, which is usually the name of the function
  created from it. Code created by the `compile()` function has the
  name `'<module>'`.

``filename``
  A string: The name of the source file from which the bytecode was compiled.

``firstlineno``
  An int: The number of the first line in the source file from which the
  bytecode was compiled.

``docstring``
  A string: The docstring for functions created from this code.


### Methods ###

These are the Code class methods.

``Code.from_code(code) -> new Code object``
  This is a class method which creates a new Code object from a raw Python code object.
  It is equivalent to the raw code object, that is, the resulting
  Code object can be converted to a new Python code object that will
  have exactly the same behaviour as the original object.

``Code.to_code() -> new code object``
  This method takes the contents of its Code instance and compiles it into
  a Python code object, and returns that object.

``code1.__eq__(code2) -> bool``
  Different Code objects can be meaningfully tested for equality. This tests
  that all attributes have the same value. For the code attribute, labels are
  compared to see if they form the same flow graph.

## Stack-depth Calculation ##

What was described above is enough for using byteplay.
However, if you apply `to_code()` and get an "Inconsistent code" exception,
or if you just want to learn more about Python's stack behaviour,
this section is for you.

When assembling code objects, the code's maximum stack usage is needed.
This is simply the maximum number of items expected on the frame's stack
while the code is executing.
If the actual number of items in stack exceeds this,
Python may well fail with a segmentation fault.
The question is then, how to calculate the maximum stack usage of a given code sequence?

There's most likely no general solution for this problem.
However, code generated by Python's compiler has a nice property which makes
it relatively easy to calculate the maximum stack usage.
The property is that if we take a bytecode "line",
and check the stack state whenever we reach that line,
we will find the stack state when we reach that line is always the same,
no matter how we got to that line.
We'll call such code "regular".

So what is the "stack state" which is always the same, exactly?
Obviously, the stack doesn't always contain the same objects when we reach a line.
For now, we can assume that it simply means the number of items on the stack.

This helps us a lot.
If we know that every line can have exactly one stack state,
and we know how every opcode changes the stack state,
we can trace stack states along all possible code paths
and find the stack state of every reachable line.
Then we can simply note which state had the largest number of stack items,
and that's the maximum stack usage of the code.
What will happen with code not generated by Python's compiler,
if it doesn't fulfill the requirement that every line should have one state?
When tracing the stack state for every line,
we will find a line that can be reached from several places,
whose stack state changes according to the address from which we jumped to that line.
In that case, an "Inconsistent code" exception will be raised.

Ok, what is really what we called "stack state"?
If every opcode pushed and popped a constant number of elements,
the stack state could have been the number of items on stack.
However, life isn't that simple.
In real life, there are *blocks*.
Blocks allow us to break from a loop,
regardless of exactly how many items we have in stack.
How? Simple.
Before the loop starts, the SETUP\_LOOP opcode is executed.
This opcode records in a block the number of operands (items) currently on the stack,
and also a position in the code.
At the end of the loop is a POP\_BLOCK opcode.
When it is executed,
the stack is restored to the recorded state by popping any extra items.
Then the corresponding block is discarded.
But if the BREAK\_LOOP opcode is executed instead of POP\_BLOCK,
one more thing happens.
The execution jumps to the position specified by the SETUP\_LOOP opcode.
Fortunately, we can still live with that.
Instead of defining the stack state as a single number,
the total number of elements in the stack,
we will define the stack state as a _sequence_ of numbers:
the number of elements in the stack per each block.
So, for example, if the state was (3, 5), 
after a BINARY\_ADD operation the state will be (3, 4)
because the operation pops two elements and pushes one element.
If the state was (3, 5),
after a PUSH\_BLOCK operation the state will be (3, 5, 0),
because a new block, without elements yet, was pushed.

Another complication: the SETUP\_FINALLY opcode specifies an address to jump to
if an exception is raised or a BREAK\_LOOP operation was executed.
This address can also be reached by normal flow.
However, the stack state on reaching that address will be different
depending on what actually happened.
If an exception was raised, 3 elements will be pushed;
if BREAK\_LOOP was executed, 2 elements will be pushed;
and if nothing happened, 1 element will be pushed by a LOAD\_CONST operation.
This seemingly non-consistent state always ends with an END\_FINALLY opcode.
The END\_FINALLY opcode pops 1, 2 or 3 elements according to what it finds on stack,
so we return to "consistent" state.
How can we deal with that complexity?

The solution is pretty simple.
We treat the SETUP\_FINALLY opcode as if it pushes 1 element to its target.
This makes it consistent with the 1 element which is pushed if the target is reached by normal flow.
However, we will calculate the stack state as if at the target line there was an opcode
which pushed 2 elements to the stack.
This is done so that the maximum stack size calculation will be correct.
Those 2 extra elements will be popped by the END\_FINALLY opcode,
which will be treated as though it always pops 3 elements.
That's all! Just be aware of that when you are playing with
SETUP\_FINALLY and END_FINALLY opcodes.

## About Freevars ##

A few words about closures in Python may be in place.
In Python, functions defined inside other functions can use variables defined
in an outer function.
We know each running function has a place to store local variables.
But how can functions refer to variables defined in an outer scope?
The solution is this: for every variable which is used in more than one scope,
a new ``cell`` object is created.
This object does one simple thing: it refers to one other object,
the value of its variable.
When the variable gets a new value, the cell object is updated too.
A reference to the cell object is passed to any function which uses that variable.
When an inner function is interested in the value of a variable of an outer scope,
it uses the value referred by the cell object passed to it.

An example might help understand this.
Let's take a look at the bytecode of a simple example::

    >>> def f():
    ...     a = 3
    ...     b = 5
    ...     def g():
    ...         return a + b
    ...
	>>> c = Code.from_code( f.__code__ )
	>>> print(c.code)

        2        1 LOAD_CONST           3
                 2 STORE_DEREF          a

        3        4 LOAD_CONST           5
                 5 STORE_DEREF          b

        4        7 LOAD_CLOSURE         a
                 8 LOAD_CLOSURE         b
                 9 BUILD_TUPLE          2
                10 LOAD_CONST           <byteplay3.Code object at 0x102793d30>
                11 LOAD_CONST           'f.<locals>.g'
                12 MAKE_CLOSURE         0
                13 STORE_FAST           g
                14 LOAD_CONST           None
                15 RETURN_VALUE         
    >>> c.code[10][1].freevars
        ('a', 'b')
    >>> print c.code[10][1].code
        5        1 LOAD_DEREF           a
                 2 LOAD_DEREF           b
                 3 BINARY_ADD
                 4 RETURN_VALUE

In the main function, opcodes 10 and 11 push the constants of
a code object and a function name on the stack.
Opcode 12, MAKE\_CLOSURE, converts that to a function.
The `from_code()` method noted this sequence and converted the
constant code object into a constant Code object by a recursive
call to `from_code()`.

We can access the value of the inner code object by indexing
the argument value of opcode 10, `c.code[10][1]`.
We can display its `freevars` attribute, and we can dump its
code in this way.

In the inner function `g()` the LOAD\_DEREF opcodes
are used to get the value of `a` and `b`.
Python knew these were defined in the outer function so it provided
cell objects pointing to them.
The LOAD\_DEREF and STORE\_DEREF opcodes access them to push the
current value onto the stack.

There is no inherent difference between cell objects
created by an outer function and cell objects used in an inner function.
What makes the difference is whether a variable name was listed in the
``freevars`` attribute of the Code object.
If it was not listed there, a new cell is created,
and if it was listed there, the cell created by an outer function is used.

We can also see how a function gets the cell objects it needs from its outer functions.
The cells for `a` and `b` are pushed onto the stack (opcodes 7 and 8).
They are made into a tuple (opcode 9).
Then the inner function is created with the MAKE\_CLOSURE opcode,
which pops three objects from the stack:
first, the function name string;
second, the code object used to create the function;
and third, the tuple of cell objects used by the code object.
We can see that the order of the cells in the tuple match the order of the
names in the ``freevars`` list.
That's how the inner function knows that `LOAD_DEREF a` means "load
the value of the first cell in the tuple".

## API Changes ##

I (Dave Cortesi) made the following changes to the public API of byteplay.

* Only Python 3.4 and above are supported.
  For Python 2.x, the original byteplay still exists and is usable.

* In the original, class `Opcode.__repr__()` and `Opcode.__str__()` had
  identical output. In byteplay3, `Opcode.__repr__()` returns a string that
  if it is eval'd, will reproduce the Opcode object. `Opcode.__str__()`,
  as before, returns the string form of the integer value.
  Note that the pretty-print module uses `repr()` to display values,
  so if you use pretty-print to display a CodeList, it will display as
  a sequence of `(Opcode(n),arg)` tuples.
  The print function uses `str()` so printing items from a CodeList
  displays `(OPCODE_NAME, arg)` tuples.

* The `printcodelist()` function accepts any of a CodeList (as before),
  a Code object, a Python code object, or a Python function object.
  Thus it can be used as a replacement for the `dis.dis` module to print
  a disassembly of any Python code. Also if `printcodelist()` output
  is directed to a binary file, it is automatically encoded UTF-8.

* I have added the function `stack_effect(Opcode, arg)` to yield the 
  _net stack change_ of that Opcode and argument. This calls on the function
  of the same name in the `opcode` module, which in turn calls on an 
  internal CPython routine in `compile.c`. As such it is fast and also
  maintained from release to release.

* The function `getse(Opcode, arg)` from the original, yielding a stack
  effect tuple (pop\_count, push\_count), is retained but now it internally
  uses `stack_effect()`, so it does not necessarily return the same
  pop and push counts as before.
  For example, if it previously returned (3,2) (pop three, push two)
  it will now return (1,0), which is simply a translation of the
  output of `stack_effect()` reporting -1.
  
  This change allowed getting rid of 200+ lines of code adapted from the
  bytecode assembly module that was difficult to maintain (or read).

* Added are the functions `object_attributes(thing)`,
  `print_object_attributes( thing, heading=None, file=None)` and
  `print_attr_values(thing, all=False, heading=None, file=None)`,
  which I found useful in understanding function and code objects.

## History ##

The original byteplay module was written by Noam Raph.
The original code can be found,
archived and frozen, at [google code](http://code.google.com/p/byteplay).

It is also available from [pypi](https://pypi.python.org/pypi/byteplay/0.2)
where it was uploaded on 2010-09-14.
In the Pypi doc (on which this doc is based), Noam wrote,

> I wrote it because I needed to manipulate Python bytecode,
> but didn't find any suitable tool.
> Michael Hudson's bytecodehacks (http://bytecodehacks.sourceforge.net/) could have worked fine for me,
> but it only works with Python 1.5.2.
> I also looked at Phillip J. Eby's peak.util.assembler (http://pypi.python.org/pypi/BytecodeAssembler),
> but it's intended at creating new code objects from scratch,
> not for manipulating existing code objects.
> So I wrote byteplay.
