import queue


def scan(code_str):
    return code_str.replace("(", " ( ").replace(")", " ) ").split()


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


class SymbolTable:

    def __init__(self):
        self.symbol_dict = {}

    def get_new_symbol(self, var):
        self.symbol_dict[var] = self.symbol_dict.get(var, 0) + 1
        return var + "." + str(self.symbol_dict[var])


class Environment:

    def __init__(self, old_env, key, new_name):
        self.old_env = old_env
        self.key = key
        self.new_name = new_name
    
    def find(self, key):
        if key == self.key:
            return self.new_name
        else:
            return self.old_env.find(key)


class Compiler:

    def __init__(self):
        self.symbol_dict = SymbolTable()
    
    def do_compile(self, code_str):
        

    def uniquify(self, exp, env):
        exp_type = type(exp)
        if exp_type == str:
            return env.find(exp)
        elif exp_type == int:
            return exp
        elif exp_type == list:
            op = exp[0]
            if op == "+":
                arg1 = self.uniquify(exp[1], env)
                arg2 = self.uniquify(exp[2], env)
                return ["+", arg1, arg2]
            elif op == "let":
                let_value = self.uniquify(exp[1][1], env)
                var = exp[1][0]
                new_name = self.symbol_dict.get_new_symbol(var)
                new_env = Environment(env, var, new_name)
                return ["let", [new_name, let_value], self.uniquify(exp[2], new_env)]

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
                add_exp1 = mark_val(value[1])
                add_exp2 = mark_val(value[2])
                if add_exp1[0] != "var":
                    add_exp1, add_exp2 = add_exp2, add_exp1
                new_op_lst.append(("movq", add_exp1, ("var", var)))
                new_op_lst.append(("addq", add_exp2, ("var", var)))
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

# code = "1"
# code = "(let (x (let (x 100000000) (+ x 200000000))) (+ x 300000000))"
code = "(let (x (let (x 100000000) (+ 200000000 x))) (+ x 300000000))"

def print_op_lst(stage, op_lst):
    print(stage)
    for op in op_lst:
        print(op)
    print("")

ast = parse(scan(code))
print(ast)

print("\n[Unify]")
symbol_dict = Symbols()
u_ast = uniquify(ast, None, symbol_dict)
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

stack_frame = StackFrame()
assign_home_op_lst = assign_home(select_op_lst, liveness_lst, stack_frame)
print("\n[STACK POS]")
print(stack_frame.symbol_pos_dict)
print("")

print_op_lst("[ASSIGN HOME]", assign_home_op_lst)

patch_op_lst = patch_instuction(assign_home_op_lst)
print_op_lst("[PATCH OP]", patch_op_lst)

print_x84_64(patch_op_lst, stack_frame)
