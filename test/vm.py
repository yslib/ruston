from opcode import hasconst
from types import CodeType
import types
from typing import Collection, List, Any, Dict
import collections
import dis
import operator

Block = collections.namedtuple('Block', 'type, handler, level')

class Frame:
	def __init__(self, f_code:CodeType, f_globals, f_locals, f_back):
		self.f_back:Frame = f_back
		self.f_code:CodeType = f_code
		self.stack:List[Any] = []
		self.block_stack:List = []
		if self.f_back and f_back.f_globals is f_globals:
			self.f_builtins = self.f_back.f_builtins
		else:
			try:
				self.f_builtins = f_globals['__builtins__']
				if hasattr(self.f_builtins, '__dict__'):
					self.f_builtins = self.f_builtins.__dict__
			except KeyError:
				self.f_builtins = {'None': None}

		self.f_lineno = self.f_code.co_firstlineno
		self.f_lasti:int = 0

		if f_code.co_cellvars:
			self.cells = {}
			if not f_back.cells:
				f_back.cells = {}
			for var in f_code.co_cellvars:
				# TODO::
				pass
		else:
			self.cells = None

		if f_code.co_freevars:
			if not self.cells:
				self.cells = {}
			for var in f_code.co_freevars:
				# TODO::
				pass

		self.return_value = None
		self.generator = None


class VirtualMachineError:
	def __init__(self):
		pass


class VirtualMachine:
	def __init__(self) -> None:
		self.frames:List[Frame] = []
		self.top_frame:Frame = None

	def make_frame(self, func_code, callargs={}, global_names=None, local_name=None):
		pass

	def push_frame(self, frame):
		self.frames.append(frame)
		self.top_frame = frame

	def pop_frame(self):
		self.frames.pop()
		if self.frames:
			self.top_frame = self.frames[-1]
		else:
			self.top_frame = None

	def run_frame(self, frame):
		self.push_frame(frame)
		while True:
			byte_name, arguments = self.parse_byte_and_args()
			why = self.dispatch(byte_name, arguments)

			while why and frame.block_stack:
				why = self.manage_block_stack(why)

			if why:
				break

		self.pop_frame()

		if why == 'exception':
			exc, val, tb = self.last_exception
			e = exc(val)
			e.__traceback__ = tb
			raise e

		return self.return_value

	def push_block(self, b_type, handler=None):
		self.top_frame.block_stack.append(Block(b_type, handler, len(self.top_frame.stack)))

	def pop_block(self):
		return self.top_frame.block_stack.pop()

	def unwind_block(self, block:Block):
		if block.type == 'except-handler':
			offset = 3
		else:
			offset = 0

		while len(self.top_frame.stack) > block.level + offset:
			self.pop()

		if block.type == 'except-handler':
			traceback, value, exctype = self.popn(3)
			self.last_exception = exctype, value, traceback

	def manage_block_stack(self, why):
		frame = self.top_frame
		block = frame.block_stack[-1]
		if block.type == 'loop' and why == 'continue':
			self.jump(self.return_value)
			why = None
			return why

		self.pop_block()
		self.unwind_block(block)

	def top(self):
		return self.top_frame.stack[-1]

	def pop(self):
		return self.top_frame.stack.pop()

	def push(self, *val):
		self.top_frame.stack.extend(val)

	def popn(self, n):
		if n:
			ret = self.top_frame.stack[-n:]
			self.top_frame.stack[-n:] = []
			return ret
		else:
			return []

	def parse_byte_and_args(self):
		f = self.top_frame
		opoffset = f.f_lasti
		bytecode = f.f_code.co_code[opoffset]
		f.f_lasti += 1  # next op or the start of args
		byte_name = dis.opname[bytecode]
		if bytecode >= dis.HAVE_ARGUMENT:
			# bytecode with args
			arg = f.f_code.co_code[f.f_lasti:f.f_lasti + 2]
			f.f_lasti += 2
			arg_val = arg[0] + (arg[1] * 256)
			if bytecode in dis.hasconst:
				arg = f.f_code.co_consts[arg_val]
			elif bytecode in dis.hasname:
				arg = f.f_code.co_names[arg_val]
			elif bytecode in dis.haslocal:
				arg = f.f_code.co_varnames[arg_val]
			elif bytecode in dis.hasjrel:
				arg = f.f_lasti + arg_val
			else:
				arg = arg_val
			arguments = [arg]
		else:
			arguments = []

		return bytecode, arguments


	def dispatch(self, byte_name:str, arguments):
		""" execute the given byte code

		Args:
			byte_name (str): python byte code string
			arguments (List[Any]): arguments list

		Raises:
			VirtualMachineError: unknown instruction encountered

		Returns:
			str: the log ouput by the execution of the instruction
		"""
		fn = getattr(self, 'byte_%s' % byte_name, None)
		try:
			if fn is None:
				# TODO::
				if byte_name.startswith('UNARY_'):
					self.unaryOperator(byte_name[:6])
				elif byte_name.startswith('BINARY_'):
					self.binaryOperator('BINARY_'[:7])
				else:
					raise VirtualMachineError
			else:
				why = fn(*arguments)
		except:
			import sys
			self.last_exception = sys.exc_info()[:2] + (None, )
			why = 'exception'

		return why

	def run_code(self):
		pass

	def jump(self, address):
		pass

	# Instructions function
	def byte_LOAD_CONST(self, const):
		self.push(const)

	def byte_POP_TOP(self):
		self.pop()

	def byte_LOAD_NAME(self, name):
		frame = self.top_frame
		if name in frame.f_locals:
			val = frame.f_locals[name]
		elif name in frame.f_globals:
			val = frame.f_globals[name]
		elif name in frame.f_builtins:
			val = frame.f_builtins[name]
		else:
			raise NameError("name %s is not defined" % name)
		self.push(val)

	def byte_STORE_NAME(self, name):
		self.top_frame.f_locals[name] = self.pop()

	def byte_LOAD_FAST(self, name):
		if name in self.top_frame.f_locals:
			val = self.top_frame.f_locals[name]
		else:
			raise UnboundLocalError("local variable %s referenced before assignement" % name)
		self.push(val)

	def byte_STORE_FAST(self, name):
		self.top_frame.f_locals[name] = self.pop()

	def byte_LOAD_GLOBAL(self, name):
		f = self.top_frame
		if name in f.f_globals:
			val = f.f_globals[name]
		elif name in f.f_builtins:
			val = f.f_builtins[name]
		else:
			raise NameError('global name %s is not defined' % name)

		self.push(val)

	BINARY_OPERATORS = {
		'POWER': pow,
		'MULTIPLY': operator.mul,
		'ADD': operator.add,
	}

	def binaryOperator(self, op):
		x, y = self.popn(2)
		self.push(self.BINARY_OPERATORS[op](x, y))

	COMPARE_OPERATORS = [
		operator.lt,
		operator.le,
		operator.eq,
		operator.ne,
		operator.gt,
		operator.ge,
		lambda x, y: x in y,
		lambda x, y: x not in y,
		lambda x, y: x is y,
		lambda x, y: x is not y,
		lambda x, y: issubclass(x, Exception) and issubclass(x, y)
	]

	def byte_COMPARE_OP(self, opnum):
		x, y = self.popn(2)
		self.push(self.COMPARE_OPERATORS[opnum](x, y))

	def byte_MAKE_FUNCTION(self, argc):
		name = self.pop()
		code = self.pop()
		defaults = self.popn(argc)
		globs = self.top_frame.f_globals
		fn = Function(name, code, globs, defaults, None, self)
		self.push(fn)

	def byte_CALL_FUNCTION(self, arg):
		lenKw, lenPos = divmod(arg, 256)
		posargs = self.popn(lenPos)

		func = self.pop()
		retval = func(*posargs)
		self.push(retval)

	def byte_RETURN_VALUE(self):
		self.return_value = self.pop()
		return 'return'

	def unaryOperator(self, op):
		pass


class Function:
	def __init__(self, name:str, code:CodeType, globs, default, closure, vm:VirtualMachine):
		"""[summary]

		Args:
			name ([type]): function name
			code ([type]): function code object
			globs ([type]): [description]
			default ([type]): defatul args
			closure ([type]): [description]
			vm ([type]): VirtualMachine object
		"""
		self._vm = vm

		self.func_code = code
		self.func_globals = globs
		self.func_name = name or code.co_name
		self.func_closure = closure

		self.__dict__ = {}
		self.__doc__ = code.co_consts[0] if code.co_consts else None

		kw = {}

		self._func = types.FunctionType(self.func_code, self.func_globals, **kw)

	def __call__(self, *args: Any, **kwds: Any) -> Any:
		import inspect
		callargs = inspect.getcallargs(self._func, *args, **kwds)
		frame = self._vm.make_frame(self.func_code, callargs, self.func_globals)
		return self._vm.run_frame(frame)

def make_cell(value):
	return (lambda x: lambda: x)(value).__closure__[0]

if __name__ == '__main__':

	def foo(a):
		b = a + 1
		def bar():
			c = b + 4
			return 1
		return bar