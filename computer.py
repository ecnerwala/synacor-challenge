import sys
import itertools

from types import MethodType

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, flush=True, **kwargs)

class FunctionArray(list):
    def __get__(self, instance, owner):
        return self.MethodView(self, instance) if instance else self

    class MethodView(list):
        def __init__(self, base, instance):
            self.base = base
            self.instance = instance
        def __len__(self):
            return len(self.base)
        def __getitem__(self, i):
            return MethodType(self.base[i], self.instance)
        def __str__(self):
            return f'<bound list of {self.base.__str__()}>'
        def __repr__(self):
            return f'<bound list of {self.base.__repr__()}>'

class Computer:
    __slots__ = ('num_steps', 'eip', 'regs', 'stack', 'mem', 'istream', 'cur_line', 'ostream', 'debug')
    MOD = 1 << 15
    MSK = MOD-1
    R0 = MOD + 0
    R1 = MOD + 1
    R2 = MOD + 2
    R3 = MOD + 3
    R4 = MOD + 4
    R5 = MOD + 5
    R6 = MOD + 6
    R7 = MOD + 7

    def __init__(self, istream=sys.stdin, ostream=sys.stdout):
        self.num_steps = 0
        self.eip = 0
        self.regs = [0] * 8
        self.stack = []
        self.mem = [0] * self.MOD
        self.cur_line = None
        self.istream = istream
        self.ostream = ostream
        self.debug = False
    
    def debug_print(self, *args, **kwargs):
        if self.debug:
            eprint(f'Step {self.num_steps}:', *args, **kwargs)

    def get_lit(self, literal):
        if literal < self.MOD:
            return literal
        elif literal < self.MOD + 8:
            if literal == self.R7:
                self.debug_print(f"Getting R7 = {self.regs[7]}")
            return self.regs[literal - self.MOD]
        else:
            raise RuntimeError('literal out of bounds')
    def set_lit(self, literal, value):
        assert 0 <= value < self.MOD
        if self.MOD <= literal < self.MOD + 8:
            if literal == self.R7:
                self.debug_print(f"Setting R7 = {value}")
            self.regs[literal - self.MOD] = value
        elif literal < self.MOD:
            raise RuntimeError('Cannot set a numeric literal')
        else:
            raise RuntimeError('literal out of bounds')
    
    def load(self, f):
        """ Load a file opened in binary mode """
        if isinstance(f, str):
            with open(f, 'rb') as g:
                self.load(g)
                return
        mem = f.read(self.MOD * 2)
        for ind, (i,j) in enumerate(zip(mem[0::2], mem[1::2])):
            v = (j << 8) | i
            self.mem[ind] = v

    def op_halt(self):
        return -1
    def op_set(self, a, b):
        self.set_lit(a, self.get_lit(b))
    def op_push(self, a):
        self.stack.append(self.get_lit(a))
    def op_pop(self, a):
        self.set_lit(a, self.stack.pop())
    def op_eq(self, a, b, c):
        self.set_lit(a, 1 if self.get_lit(b) == self.get_lit(c) else 0)
    def op_gt(self, a, b, c):
        self.set_lit(a, 1 if self.get_lit(b) > self.get_lit(c) else 0)
    def op_jmp(self, a):
        return self.get_lit(a)
    def op_jt(self, a, b):
        if self.get_lit(a):
            return self.get_lit(b)
    def op_jf(self, a, b):
        if not self.get_lit(a):
            return self.get_lit(b)
    def op_add(self, a, b, c):
        self.set_lit(a, (self.get_lit(b) + self.get_lit(c)) & self.MSK)
    def op_mult(self, a, b, c):
        self.set_lit(a, (self.get_lit(b) * self.get_lit(c)) & self.MSK)
    def op_mod(self, a, b, c):
        self.set_lit(a, (self.get_lit(b) % self.get_lit(c)) & self.MSK)
    def op_and(self, a, b, c):
        self.set_lit(a, (self.get_lit(b) & self.get_lit(c)) & self.MSK)
    def op_or(self, a, b, c):
        self.set_lit(a, (self.get_lit(b) | self.get_lit(c)) & self.MSK)
    def op_not(self, a, b):
        self.set_lit(a, (~self.get_lit(b)) & self.MSK)
    def op_rmem(self, a, b):
        self.set_lit(a, self.mem[self.get_lit(b)])
    def op_wmem(self, a, b):
        self.mem[self.get_lit(a)] = self.get_lit(b)
    def op_call(self, a):
        self.stack.append(self.eip)
        return self.get_lit(a)
    def op_ret(self):
        if not self.stack:
            return -1
        return self.stack.pop()
    def op_out(self, a):
        c = chr(self.get_lit(a))
        self.ostream.write(c)
        if c == '\n':
            self.ostream.flush()
            self.debug_print(f'Output flushed')
    def op_in(self, a):
        if not self.cur_line:
            eprint(f'Step {self.num_steps}: Input')
            if self.istream is sys.stdin:
                self.cur_line = input() + '\n'
            else:
                self.cur_line = self.istream.readline()
            if not self.cur_line:
                raise RuntimeError('Hit EOF!')
            eprint('>>> '+self.cur_line[:-1]) # Strip the '\n'
        self.set_lit(a, ord(self.cur_line[0]))
        self.cur_line = self.cur_line[1:]
    def op_noop(self):
        pass

    class Op:
        __slots__ = ('opcode', 'name', 'nargs', 'fn')
        def __init__(self, opcode, fn, nargs):
            self.opcode = opcode
            self.name = fn.__name__
            self.nargs = nargs
            self.fn = fn
        def __call__(self, instance, *args, **kwargs):
            return self.fn(instance, *args, **kwargs)
        def __get__(self, instance, owner):
            return MethodType(self, instance) if instance else self

    ops = FunctionArray([
        Op( 0, op_halt, 0),
        Op( 1,  op_set, 2),
        Op( 2, op_push, 1),
        Op( 3,  op_pop, 1),
        Op( 4,   op_eq, 3),
        Op( 5,   op_gt, 3),
        Op( 6,  op_jmp, 1),
        Op( 7,   op_jt, 2),
        Op( 8,   op_jf, 2),
        Op( 9,  op_add, 3),
        Op(10, op_mult, 3),
        Op(11,  op_mod, 3),
        Op(12,  op_and, 3),
        Op(13,   op_or, 3),
        Op(14,  op_not, 2),
        Op(15, op_rmem, 2),
        Op(16, op_wmem, 2),
        Op(17, op_call, 1),
        Op(18,  op_ret, 0),
        Op(19,  op_out, 1),
        Op(20,   op_in, 1),
        Op(21, op_noop, 0),
    ])
    
    def parse_text(self, start_pos=None, num_bytes=40):
        if start_pos is None:
            start_pos = self.eip
        elif start_pos < 0:
            start_pos = self.eip - start_pos
        cur_pos = start_pos
        while cur_pos < start_pos + num_bytes:
            loc = cur_pos
            i = self.mem[cur_pos]
            cur_pos += 1
            if not 0 <= i < len(self.ops):
                print(f'{loc}: ILLOP {i}')
                continue
            op = self.ops[i]
            s = f'{loc}: {op.name}'
            try:
                for _ in range(op.nargs):
                    arg = self.mem[cur_pos]
                    cur_pos += 1
                    if arg < self.MOD:
                        if arg >= self.MOD / 2:
                            arg -= self.MOD
                        arg = str(arg)
                    elif arg < self.MOD + 8:
                        arg = 'R'+str(arg - self.MOD)
                    else:
                        arg = f'?{arg}/R{arg-self.MOD}'
                    s += ' ' + arg
            except IndexError:
                s += ' EOM'
            print(s)

    def step(self):
        if self.eip == -1:
            raise RuntimeError('Computer halted')

        cur_eip = self.eip

        opcode = self.mem[self.eip]
        self.eip += 1

        op = self.ops[opcode]
        
        args = self.mem[self.eip:self.eip + op.nargs]
        self.eip += op.nargs
        
        neip = op(*args)
        if neip is not None:
            self.eip = neip

        self.num_steps += 1

    def run(self, num_steps=None, *, max_step=None, istream=None, ostream=None):
        if istream is not None:
            self.istream = istream
        if ostream is not None:
            self.ostream = ostream
        if max_step is not None:
            num_steps = max_step - self.num_steps
        for _ in (itertools.count() if num_steps is None else range(num_steps)):
            self.step()