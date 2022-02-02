import sys

def debug(str):
    print(str, file=sys.stderr)

def scan(code):
    return code.replace("(", " ( ").replace(")", " ) ").split()

def parse(tokens):
    if len(tokens) == 0:
        raise SyntaxError("Parse Err: Unexpected EOF")
    token = tokens.pop(0)
    if token == '(':
        exp_lst = [tokens.pop(0)]       # op
        while tokens[0] != ')':
            exp_lst.append(parse(tokens))
        tokens.pop(0)    # pop off ')'
        return exp_lst
    elif token == ')':
        raise SyntaxError('Parse Err: Unexpected )')
    elif token[0].isdigit() or token[0] == "-":
        return ["int", int(token)]
    else:
        return ["var", token]

class Symbols:
    symbol_dict = {}

    @staticmethod
    def get_new_symbol(var):
        if var not in Symbols.symbol_dict:
            Symbols.symbol_dict[var] = 1
        else:
            Symbols.symbol_dict[var] += 1
        return var + "." + str(Symbols.symbol_dict[var])

class Senv:

    def __init__(self, old_env, key, new_name):
        self.old_env = old_env
        self.key = key
        self.new_name = new_name
    
    def find(self, key):
        if key == self.key:
            return self.new_name
        else:
            return self.old_env.find(key)

def trans_operand_to_str(operand):
    match operand:
        case ["int", i]:
            return "$" + str(i)
        case ["deref", reg, offset]:
            return "{}(%{})".format(offset, reg)
        case ["reg", reg]:
            return "%" + reg

class BasicBlock:

    def __init__(self, block_name, next_block):
        self.block_name = block_name
        self.next_block = next_block
        self.inst_lst = []
    
    def append(self, op):
        self.inst_lst.append(op)

    def __str__(self):
        rest = self.block_name + "\n"
        for op in self.inst_lst:
            rest += "\t" + str(op) + "\n"
        return rest
    
    def print_code(self):
        print("_" + self.block_name + ":")
        for inst in self.inst_lst:
            match inst:
                case ["callq", ["func", func]]:
                    print("    callq _{}".format(func))
                case _:
                    print("    {} {}, {}".format(inst[0], trans_operand_to_str(inst[1]), trans_operand_to_str(inst[2])))
        print("    jmp _" + self.next_block)
        

class StackFrame:

    def __init__(self):
        self.symbol_pos_dict = {}
        self.frame_len = 0

    def get_var_pos(self, arg):
        if arg[0] != "var":
            return arg
        var = arg[1]
        if var not in self.symbol_pos_dict:
            self.symbol_pos_dict[var] = self.frame_len
            self.frame_len += 1
        pos = self.symbol_pos_dict[var]
        return ("deref", "rbp", -8 * (pos + 1))
    
    def get_frame_size(self):
        frame_size = self.frame_len 
        if frame_size % 2 == 1:
            frame_size += 1
        return frame_size * 8

def uniquify(exp, env):
    match exp:
        case ["read"]:
            return exp
        case ["var", var]:
            return ["var", env.find(var)]
        case ["int", i]:
            return exp
        case ["+", arg1, arg2]:
            new_arg1 = uniquify(arg1, env)
            new_arg2 = uniquify(arg2, env)
            return ["+", new_arg1, new_arg2]
        case ["let", [var, value], let_exp]:
            new_value = uniquify(value, env)
            new_var = Symbols.get_new_symbol(var)
            new_env = Senv(env, var, new_var)
            return ["let", [new_var, new_value], uniquify(let_exp, new_env)]

def flatten(exp, dest, bb):
    match exp:
        case ["read"]:
            bb.append(["assign", dest, ["func", "read_int"]])
        case [("var" | "int"), _]:
            bb.append(["assign", dest, exp])
        case ["+", arg1, arg2]:
            if arg1[0] not in ("int", "var"):
                tmp_var = ["var", Symbols.get_new_symbol("tmp")]
                flatten(arg1, tmp_var, bb)
                arg1 = tmp_var
            if arg2[0] not in ("int", "var"):
                tmp_var = ["var", Symbols.get_new_symbol("tmp")]
                flatten(arg2, tmp_var, bb)
                arg2 = tmp_var
            bb.append(["assign", dest, ["+", arg1, arg2]])
        case ["let", [var, value], let_exp]:
            flatten(value, ["var", var], bb)
            flatten(let_exp, dest, bb)

def select_instruction(bb):
    old_inst_lst = bb.inst_lst
    bb.inst_lst = []
    for inst in old_inst_lst:
        match inst:
            case [_, dest, ["+", arg1 ,arg2]]:
                bb.append(["movq", arg1, dest])
                bb.append(["addq", arg2, dest])
            case [_, dest, ["func", func]]:
                bb.append(["callq", ["func", func]])
                bb.append(["movq", ["reg", "rax"], dest])
            case [_, dest, src]:
                bb.append(["movq", src, dest])

def assign_home(bb, sf):
    old_inst_lst = bb.inst_lst
    bb.inst_lst = []
    for inst in old_inst_lst:
        match inst:
            case [op, arg1, arg2]:
                bb.append([op, sf.get_var_pos(arg1), sf.get_var_pos(arg2)])
            case [op, arg1]:
                bb.append([op, sf.get_var_pos(arg1)])

def patch_instruction(bb):
    old_inst_lst = bb.inst_lst
    bb.inst_lst = []
    for inst in old_inst_lst:
        match inst:
            case [op, ["deref", var1, offset1], ["deref", var2, offset2]]:
                bb.append(["movq", ["deref", var1, offset1], ["reg", "rax"]])
                bb.append([op, ["reg", "rax"], ["deref", var2, offset2]])
            case default:
                bb.append(inst)

def print_x84_64(bb, sf):
    print("    .global _main")
    print("_main:")
    print("    pushq %rbp")
    print("    movq %rsp, %rbp")
    if sf.get_frame_size() > 0:
        print("    subq $" + str(sf.get_frame_size()) + ", %rsp")
    print("    jmp _{}".format(bb.block_name))
    print("_conclusion:")
    if sf.get_frame_size() > 0:
        print("    addq $" + str(sf.get_frame_size()) + ", %rsp")
    print("    popq %rbp")
    print("    retq")
    
    bb.print_code()

code = sys.stdin.read()

ast = parse(scan(code))
debug(ast)

debug("\n[Unify]")
u_ast = uniquify(ast, None)
debug(u_ast)

debug("\n[Flatten]")
start_bb = BasicBlock("start", "conclusion")
flatten(u_ast, ["reg", "rax"], start_bb)
debug(start_bb)

debug("\n[SELECT INSTRUCTION]")
select_instruction(start_bb)
debug(start_bb)

debug("\n[ASSIGN HOME]")
sf = StackFrame()
assign_home(start_bb, sf)
debug(start_bb)

debug("\n[PATCH INSTRUCTION]")
patch_instruction(start_bb)
debug(start_bb)

print_x84_64(start_bb, sf)
