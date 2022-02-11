
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

class Flatten:
    def __init__(self, exp):
        self.exp = exp
        self.op_lst = []
    
    def flatten(self, exp):
        exp_type = type(exp)
        if exp_type in (int, str):
            return exp
        elif exp_type == list:
            if exp[0] == "+":
                exp1 = self.flatten(exp[1])
                exp2 = self.flatten(exp[2])
                tmp_var = Symbols.get_new_symbol("tmp")
                self.op_lst.append(("assign", tmp_var, ("+", exp1, exp2)))
                return tmp_var
        raise SyntaxError('Flatten Err: Unkown Exp {}'.format(exp))

    def run(self):
        final_exp = self.flatten(self.exp)
        self.op_lst.append(("return", final_exp))

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
            add_exp = inst[2]
            add_exp1 = add_exp[1]
            add_exp2 = add_exp[2]
            new_op_lst.append(("movq", mark_val(add_exp1), ("var", var)))
            new_op_lst.append(("addq", mark_val(add_exp2), ("var", var)))
        elif inst[0] == "return":
            new_op_lst.append(("movq", mark_val(inst[1]), ("reg", "rax")))
    return new_op_lst

class StackFrame:
    symbol_pos_dict = {}
    frame_size = 0

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
    print("    addq $" + str(StackFrame.frame_size) + ", %rsp")
    print("    popq %rbp")
    print("    retq")

# code = "1"
code = "(+ (+ 1 2) (+ 3 4))"

def print_op_lst(stage, op_lst):
    print(stage)
    for op in op_lst:
        print(op)
    print("")

ast = parse(scan(code))
print(ast)

flatten_obj = Flatten(ast)
flatten_obj.run()
flatten_op_lst = flatten_obj.op_lst
print_op_lst("[Flatten]", flatten_op_lst)

select_op_lst = select_instruction(flatten_op_lst)
print_op_lst("[SELECT OP]", select_op_lst)

assign_home_op_lst = assign_home(select_op_lst)
print_op_lst("[ASSIGN HOME]", assign_home_op_lst)

patch_op_lst = patch_instuction(assign_home_op_lst)
print_op_lst("[PATCH OP]", patch_op_lst)

print_x84_64(patch_op_lst)
