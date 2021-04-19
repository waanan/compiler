
def scan(code):
    return code.replace("(", " ( ").replace(")", " ) ").split()

def parse(tokens):
    if len(tokens) == 0:
        raise SyntaxError("Parse Err: Unexpected EOF")
    token = tokens.pop(0)
    if token == '(':
        exp_lst = []
        while tokens[0] != ')':
            exp_lst.append(parse(tokens))
        tokens.pop(0)    # pop off ')'
        return exp_lst
    elif token == ')':
        raise SyntaxError('Parse Err: Unexpected )')
    elif token[0].isdigit() or token[0] == "-":
        return int(token)
    else:
        return token

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

def uniquify(exp, env):
    exp_type = type(exp)
    if exp_type == str:
        return env.find(exp)
    elif exp_type == int:
        return exp
    elif exp_type == list:
        op = exp[0]
        if op == "+":
            arg1 = uniquify(exp[1], env)
            arg2 = uniquify(exp[2], env)
            return ["+", arg1, arg2]
        elif op == "let":
            let_value = uniquify(exp[1][1], env)
            var = exp[1][0]
            new_name = Symbols.get_new_symbol(var)
            new_env = Senv(env, var, new_name)
            return ["let", [new_name, let_value], uniquify(exp[2], new_env)]

class Flatten:
    def __init__(self, exp):
        self.exp = exp
        self.op_lst = []
    
    def exp_to_simple(self, exp):
        exp_type = type(exp)
        if exp_type in (int, str):
            return exp
        elif exp_type == list:
            if exp[0] == "+":
                exp1 = self.exp_to_simple(exp[1])
                exp2 = self.exp_to_simple(exp[2])
                if type(exp1) not in (int, str):
                    tmp_var = Symbols.get_new_symbol("tmp")
                    self.op_lst.append(("assign", tmp_var, exp1))
                    exp1 = tmp_var
                if type(exp2) not in (int, str):
                    tmp_var = Symbols.get_new_symbol("tmp")
                    self.op_lst.append(("assign", tmp_var, exp2))
                    exp2 = tmp_var                
                return "+", exp1, exp2
            elif exp[0] == "let":
                simple_let_value= self.exp_to_simple(exp[1][1])
                self.op_lst.append(("assign", exp[1][0], simple_let_value))
                return self.exp_to_simple(exp[2])
        raise SyntaxError('Flatten Err: Unkown Exp {}'.format(exp))

    def run(self):
        final_exp = self.exp_to_simple(self.exp)
        if type(final_exp) in (int, str):
            self.op_lst.append(("return", final_exp))
        else:
            tmp_var = Symbols.get_new_symbol("tmp")
            self.op_lst.append(("assign", tmp_var, final_exp))
            self.op_lst.append(("return", tmp_var))

def mark_val(val):
    if type(val) == int:
        return "int", val
    else:
        return "var", val

def select_instruction(op_lst):
    new_op_lst = []
    for inst in op_lst:
        if inst[0] == "assign":
            var = inst[1]
            value = inst[2]
            if type(value) in (int, str):
                new_op_lst.append(("movq", mark_val(value), ("var", var)))
            elif value[0] == "+":
                add_exp1 = value[1]
                add_exp2 = value[2]
                new_op_lst.append(("movq", mark_val(add_exp1), ("var", var)))
                new_op_lst.append(("addq", mark_val(add_exp2), ("var", var)))
        elif inst[0] == "return":
            new_op_lst.append(("movq", mark_val(inst[1]), ("reg", "rdi")))
    return new_op_lst

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
    return reversed(live_after_lst)

class StackFrame:
    symbol_pos_dict = {}
    frame_size = 0
    alloc_reg_lst = ["rcx", "rdx"]

def get_var_pos(arg):
    if arg[0] == "var":
        return ("deref", "rbp", StackFrame.symbol_pos_dict[arg[1]])
    else:
        return arg

def assign_home(op_lst):
    base = 0
    for var, count in Symbols.symbol_dict.items():
        StackFrame.frame_size += 8 * count
        for i in range(count):
            base = base - 8
            StackFrame.symbol_pos_dict[var + "." + str(i+1)] = base
    if StackFrame.frame_size % 16 != 0:
        StackFrame.frame_size += 8
    new_op_lst = []
    for inst in op_lst:
        new_op_lst.append((inst[0], 
                            get_var_pos(inst[1]), 
                            get_var_pos(inst[2])))
    return new_op_lst

def patch_instuction(op_lst):
    new_op_lst = []
    for inst in op_lst:
        arg1 = inst[1]
        arg2 = inst[2]
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

def print_x84_64(op_lst):
    print("    .global main")
    print("main:")
    print("    pushq %rbp")
    print("    movq %rsp, %rbp")
    print("    subq $" + str(StackFrame.frame_size) + ", %rsp")
    for inst in op_lst:
        print("    " + inst[0] + " " + trans_operand_to_str(inst[1]) + ", " + trans_operand_to_str(inst[2]))
    print("    callq print_int")
    print("    movq $0, %rax")
    print("    addq $" + str(StackFrame.frame_size) + ", %rsp")
    print("    popq %rbp")
    print("    retq")

# code = "1"
code = "(let (x 1) (let (y 2) (+ x y)))"

def print_op_lst(stage, op_lst):
    print(stage)
    for op in op_lst:
        print(op)
    print("")

ast = parse(scan(code))
print(ast)

print("\n[Unify]")
u_ast = uniquify(ast, None)
print(u_ast)
print("")

flatten_obj = Flatten(u_ast)
flatten_obj.run()
flatten_op_lst = flatten_obj.op_lst
print_op_lst("[Flatten]", flatten_op_lst)

select_op_lst = select_instruction(flatten_op_lst)
print_op_lst("[SELECT OP]", select_op_lst)

liveness_lst = cal_liveness(select_op_lst)
print_op_lst("[LIVENESS ANALYZE]", liveness_lst)

assign_home_op_lst = assign_home(select_op_lst)
print_op_lst("[ASSIGN HOME]", assign_home_op_lst)

patch_op_lst = patch_instuction(assign_home_op_lst)
print_op_lst("[PATCH OP]", patch_op_lst)

print_x84_64(patch_op_lst)
