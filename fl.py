import queue

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

class BasicBlock:

    def __init__(self, block_name):
        self.block_name = block_name
        self.inst_lst = []
    
    def append(self, op):
        self.inst_lst.append(op)

    def __str__(self):
        rest = self.block_name + "\n"
        for op in self.inst_lst:
            rest += "\t" + str(op) + "\n"
        return rest

def uniquify(exp, env):
    match exp:
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
            case [_, dest, src]:
                bb.append(["movq", src, dest])

def cal_liveness(op_lst):
    live_set = set()
    live_after_lst = [live_set]
    for op in op_lst[:0:-1]:
        new_live_set = live_set.copy()
        if op[0] == "addq":
            add_exp1 = op[1]
            add_exp2 = op[2]
            if add_exp1[0] == "var":
                new_live_set.add(add_exp1[1])
            if add_exp2[0] == "var":
                new_live_set.add(add_exp2[1])
        elif op[0] == "movq":
            from_exp = op[1]
            to_exp = op[2]
            if from_exp[0] == "var":
                new_live_set.add(from_exp[1])
            if to_exp[0] == "var":
                new_live_set.discard(to_exp[1])
        live_set = new_live_set
        live_after_lst.append(live_set)
    live_after_lst.reverse()
    return live_after_lst

class StackFrame:

    def __init__(self):
        self.symbol_pos_dict = {}
        self.pos_var_count = []
        self.frame_len = 0
        self.alloc_reg_lst = ["rcx", "rdx"]
        self.alloc_queue = queue.PriorityQueue()

    def mark_del(self, var):
        pos = self.symbol_pos_dict[var]
        self.pos_var_count[pos] -= 1
        if self.pos_var_count[pos] == 0:
            self.alloc_queue.put(pos)
    
    def alias_var(self, new_var, old_var):
        pos = self.symbol_pos_dict[old_var]
        self.symbol_pos_dict[new_var] = pos
        self.pos_var_count[pos] += 1

    def get_var_pos(self, arg):
        if arg[0] != "var":
            return arg
        var = arg[1]
        if var not in self.symbol_pos_dict:
            if self.alloc_queue.empty():
                self.symbol_pos_dict[var] = self.frame_len
                self.frame_len = self.frame_len + 1
                self.pos_var_count.append(1)
            else:
                self.symbol_pos_dict[var] = self.alloc_queue.get()
        pos = self.symbol_pos_dict[var]
        reg_num = len(self.alloc_reg_lst)
        if pos < reg_num:
            return ("reg", self.alloc_reg_lst[pos])
        else:
            return ("deref", "rbp", -8 * (pos - reg_num + 1))
    
    def get_frame_size(self):
        stack_size = self.frame_len - len(self.alloc_reg_lst)
        if  stack_size <= 0:
            return 0
        if stack_size % 2 == 1:
            stack_size += 1
        return stack_size * 8

def assign_home(op_lst, liv_lst, sf):
    new_op_lst = []
    liv_before_set = set()
    for i in range(len(op_lst)):
        inst = op_lst[i]
        liv_after = liv_lst[i]
        if inst[0] == "movq" and inst[1][0] == "var" \
            and inst[2][0] == "var" and inst[1][1] not in liv_after:
            sf.alias_var(inst[2][1], inst[1][1])
        new_op_lst.append((inst[0], 
                            sf.get_var_pos(inst[1]), 
                            sf.get_var_pos(inst[2])))
        if inst[1][0] == "var":
            liv_before_set.add(inst[1][1])
        if inst[2][0] == "var":
            liv_before_set.add(inst[2][1])
        dead_set = liv_before_set - liv_after
        for var in dead_set:
            sf.mark_del(var)
        liv_before_set = liv_after
    return new_op_lst

def patch_instuction(op_lst):
    new_op_lst = []
    for inst in op_lst:
        op = inst[0]
        arg1 = inst[1]
        arg2 = inst[2]
        if op == "movq" and arg1 == arg2:
            continue
        if arg1[0] == "deref" and arg2[0] == "deref":
            new_op_lst.append(("movq", arg1, ("reg", "rax")))
            new_op_lst.append((inst[0], ("reg", "rax"), arg2))
        else:
            new_op_lst.append(inst)
    return new_op_lst

def trans_operand_to_str(operand):
    if operand[0] == "int":
        return "$" + str(operand[1])
    elif operand[0] == "deref":
        return str(operand[2]) + "(%" + operand[1] + ")"
    elif operand[0] == "reg":
        return "%" + operand[1]

def print_x84_64(op_lst, sf):
    print("    .global main")
    print("main:")
    print("    pushq %rbp")
    print("    movq %rsp, %rbp")
    if sf.get_frame_size() > 0:
        print("    subq $" + str(sf.get_frame_size()) + ", %rsp")
    for inst in op_lst:
        print("    " + inst[0] + " " + trans_operand_to_str(inst[1]) + ", " + trans_operand_to_str(inst[2]))
    print("    callq print_int")
    print("    movq $0, %rax")
    if sf.get_frame_size() > 0:
        print("    addq $" + str(sf.get_frame_size()) + ", %rsp")
    print("    popq %rbp")
    print("    retq")

code = "1"
# code = "(let (x (let (x 100000000) (+ x 200000000))) (+ x 300000000))"
# code ="""
# (let (a 1)
#     (let (b a)
#         1)
# )
# """
# code = "(let (x (let (x 100000000) (+ 200000000 x))) (+ x 300000000))"

ast = parse(scan(code))
print(ast)

print("\n[Unify]")
u_ast = uniquify(ast, None)
print(u_ast)

print("\n[Flatten]")
start_bb = BasicBlock("start")
flatten(u_ast, ["reg", "rax"], start_bb)
print(start_bb)

print("\n[SELECT INSTRUCTION]")
select_instruction(start_bb)
print(start_bb)


# select_op_lst = select_instruction(flatten_op_lst)
# print_op_lst("[SELECT OP]", select_op_lst)

# liveness_lst = cal_liveness(select_op_lst)
# print_op_lst("[LIVENESS ANALYZE]", liveness_lst)

# stack_frame = StackFrame()
# assign_home_op_lst = assign_home(select_op_lst, liveness_lst, stack_frame)
# print("\n[STACK POS]")
# print(stack_frame.symbol_pos_dict)
# print("")

# print_op_lst("[ASSIGN HOME]", assign_home_op_lst)

# patch_op_lst = patch_instuction(assign_home_op_lst)
# print_op_lst("[PATCH OP]", patch_op_lst)

# print_x84_64(patch_op_lst, stack_frame)
