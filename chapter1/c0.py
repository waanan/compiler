
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

# code = "1"
code = "(+ (+ 1 2) (+ 3 4))"

ast = parse(scan(code))
print(ast)

flatten_obj = Flatten(ast)
flatten_obj.run()
flatten_op_lst = flatten_obj.op_lst
print(flatten_op_lst)

select_op_lst = select_instruction(flatten_op_lst)
print(select_op_lst)