import sys


def error(msg):
    print("Error! " + msg)
    sys.exit(1)


def print_op_lst(op_lst):
    for op in op_lst:
        print(op)


class LetExp:
    def __init__(self, var, var_exp, body_exp):
        self.var = var
        self.var_exp = var_exp
        self.body_exp = body_exp

    def __str__(self):
        return "(let [" + self.var + " " + \
                          str(self.var_exp).replace("\n", "\n" + " " * (len(self.var) + 7)) + \
                      "]\n  " \
                        + str(self.body_exp).replace("\n", "\n  ") + ")"


class AddExp:
    def __init__(self, exp1, exp2):
        self.exp1 = exp1
        self.exp2 = exp2

    def __str__(self):
        exp1_str = str(self.exp1) 
        if "\n" in exp1_str:
            return "(+ " + exp1_str.replace("\n", "\n   ") + "\n   " + str(self.exp2).replace("\n", "\n   ") + ")"
        else:
            return "(+ " + exp1_str + " " + str(self.exp2).replace("\n", "\n" + " " * (len(exp1_str) + 4)) + ")"


def scan(code_str):
    """
    扫描字符串，得到一个词的lst
    :param code_str:
    :return:
    """
    lst = []
    i = 0
    length = len(code_str)
    while i < length:
        letter = code_str[i]
        i = i + 1
        if letter == " ":
            continue
        elif letter in ['(', ')', '[', ']', '+']:
            lst.append(letter)
        elif "0" <= letter <= "9":
            num = int(letter)
            letter = code_str[i]
            while "0" <= letter <= "9":
                num = num * 10 + int(letter)
                i = i + 1
                letter = code_str[i]
            lst.append(num)
        elif "a" <= letter <= "z" or "A" <= letter <= "Z":
            tmp = letter
            letter = code_str[i]
            while "a" <= letter <= "z" or "A" <= letter <= "Z":
                tmp = tmp + letter
                i = i + 1
                letter = code_str[i]
            lst.append(tmp)
        else:
            print("error!" + letter)
    scanner = Scanner(lst)
    return scanner


class Scanner:
    def __init__(self, lst):
        self.pos = 0
        self.lst = lst

    def next(self):
        """
        读取下一个token
        :return:
        """
        token = self.lst[self.pos]
        self.pos = self.pos + 1
        return token

    def assert_next_reserved(self, expect_token):
        token = self.next()
        if token != expect_token:
            error("Need token {}, given {} at {}".format(expect_token, token, self.pos - 1))


def parse(scanner):
    """
    通过scanner，构建语法树
    :param scanner:
    :return:
    """
    token = scanner.next()
    if type(token) == int:
        # 对应int-exp
        return token
    elif token == "(":
        op = scanner.next()
        exp = None
        if op == "let":
            scanner.assert_next_reserved("[")
            var = scanner.next()
            var_exp = parse(scanner)
            scanner.assert_next_reserved("]")
            body_exp = parse(scanner)
            exp = LetExp(var, var_exp, body_exp)
        elif op == "+":
            exp1 = parse(scanner)
            exp2 = parse(scanner)
            exp = AddExp(exp1, exp2)
        else:
            error("Unknown op {}".format(op))
        scanner.assert_next_reserved(")")
        return exp
    else:
        # 对应var-exp
        return token


class UniEnv:
    # 记录一个符号被绑定过的次数
    symbol_dict = {}
    frame_size = 0

    def __init__(self, old_env, key, lvl):
        self.old_env = old_env
        self.key = key
        self.lvl = lvl

    @staticmethod
    def get_new_lvl(var):
        if var not in UniEnv.symbol_dict:
            UniEnv.symbol_dict[var] = 1
            return 1
        else:
            UniEnv.symbol_dict[var] += 1
            return UniEnv.symbol_dict[var]


def apply(uni_env, key):
    if uni_env is None:
        return 0
    if key == uni_env.key:
        return uni_env.lvl
    else:
        return apply(uni_env.old_env, key)


def uniquify(exp, env):
    """
    重命名exp中的变量名，处理over shadow的情况
    :param exp: 待转换的exp
    :param env: 转换需要的上下文信息
    :return:
    """
    exp_type = type(exp)
    if exp_type == str:
        lvl = apply(env, exp)
        return exp + "." + str(lvl)
    elif exp_type == int:
        return exp
    elif exp_type == LetExp:
        new_let_exp = uniquify(exp.var_exp, env)
        new_lvl = UniEnv.get_new_lvl(exp.var)
        new_env = UniEnv(env, exp.var, new_lvl)
        new_var = exp.var + "." + str(new_lvl)
        return LetExp(new_var, new_let_exp, uniquify(exp.body_exp, new_env))
    elif exp_type == AddExp:
        exp1 = uniquify(exp.exp1, env)
        exp2 = uniquify(exp.exp2, env)
        return AddExp(exp1, exp2)


class Flatten:
    def __init__(self, exp):
        self.exp = exp
        self.op_lst = []
    
    def exp_to_simple(self, exp):
        exp_type = type(exp)
        if exp_type in (int, str):
            return exp
        elif exp_type == LetExp:
            simple_var_exp = self.exp_to_simple(exp.var_exp)
            self.op_lst.append(("assign", exp.var, simple_var_exp))
            return self.exp_to_simple(exp.body_exp)
        elif exp_type == AddExp:
            exp1 = self.exp_to_simple(exp.exp1)
            exp2 = self.exp_to_simple(exp.exp2)
            if type(exp1) not in (int, str):
                tmp_var = "tmp." + str(UniEnv.get_new_lvl("tmp"))
                self.op_lst.append(("assign", tmp_var, exp1))
                exp1 = tmp_var
            if type(exp2) not in (int, str):
                tmp_var = "tmp." + str(UniEnv.get_new_lvl("tmp"))
                self.op_lst.append(("assign", tmp_var, exp2))
                exp2 = tmp_var
            return "+", exp1, exp2

    def run(self):
        final_exp = self.exp_to_simple(self.exp)
        if type(final_exp) in (int, str):
            self.op_lst.append(("return", final_exp))
        else:
            tmp_var = "tmp." + str(UniEnv.get_new_lvl("tmp"))
            self.op_lst.append(("assign", tmp_var, final_exp))
            self.op_lst.append(("return", tmp_var))


def trans_simple_exp_to_tuple(simple_exp):
    if type(simple_exp) == int:
        return "int", simple_exp
    elif type(simple_exp) == str:
        return "var", simple_exp


def select_instruction(op_lst):
    """
    转换成类似x86的语言
    :param op_lst:
    :return:
    """
    new_op_lst = []
    for inst in op_lst:
        if inst[0] == "assign":
            var = inst[1]
            simple_exp = inst[2]
            simple_exp_type = type(simple_exp)
            if simple_exp_type in (int, str):
                new_op_lst.append(("movq", trans_simple_exp_to_tuple(simple_exp), ("var", var)))
            else:
                exp1 = simple_exp[1]
                exp2 = simple_exp[2]
                if exp1 == var:
                    new_op_lst.append(("addq", trans_simple_exp_to_tuple(exp2), ("var", var)))
                elif exp2 == var:
                    new_op_lst.append(("addq", trans_simple_exp_to_tuple(exp1), ("var", var)))
                else:
                    new_op_lst.append(("movq", trans_simple_exp_to_tuple(exp1), ("var", var)))
                    new_op_lst.append(("addq", trans_simple_exp_to_tuple(exp2), ("var", var)))
        elif inst[0] == "return":
            new_op_lst.append(("movq", trans_simple_exp_to_tuple(inst[1]), ("reg", "rax")))
        else:
            error("Unknown op!")
    return new_op_lst


def get_live_set_before_op(instruction, after_live_set):
    pass


def uncover_live(op_lst):
    pass


def trans_to_home(inst_operand, var_home_dict):
    if inst_operand[0] == "var":
        return ("deref", "rbp", var_home_dict[inst_operand[1]])
    else:
        return inst_operand


def assign_home(op_lst):
    var_home_dict = {}
    base = 0
    for var, count in UniEnv.symbol_dict.items():
        UniEnv.frame_size += 8 * count
        i = 1
        while i <= count:
            base = base - 8
            var_home_dict[var + "." + str(i)] = base
            i = i + 1
    if UniEnv.frame_size % 16 != 0:
        UniEnv.frame_size += 8
    print("[Var home dict]")
    print(var_home_dict)
    new_op_lst = []
    for inst in op_lst:
        if inst[0] in ("addq", "movq"):
            new_op_lst.append((inst[0], trans_to_home(inst[1], var_home_dict), trans_to_home(inst[2], var_home_dict)))
        else:
            error("Unknown op!")
    return new_op_lst


def patch_instuction(op_lst):
    new_op_lst = []
    for inst in op_lst:
        if inst[1][0] == "deref" and inst[2][0] == "deref":
            new_op_lst.append(("movq", inst[1], ("reg", "rax")))
            new_op_lst.append((inst[0], ("reg", "rax"), inst[2]))
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
    else:
        error("Unknown operand {}".format(operand))


def print_x84_64(op_lst):
    print("    .global main")
    print("main:")
    print("    pushq %rbp")
    print("    movq %rsp, %rbp")
    print("    subq $" + str(UniEnv.frame_size) + ", %rsp")

    for inst in op_lst:
        print("    " + inst[0] + " " + trans_operand_to_str(inst[1]) + ", " + trans_operand_to_str(inst[2]))

    print("    addq $" + str(UniEnv.frame_size) + ", %rsp")
    print("    popq %rbp")
    print("    retq")


# test_code = "1"
# test_code = "(let [x 1] 1)"
# test_code = "(+ 3 (let [x 1] x))"
# test_code = "(+ (let [x 1] x) (let [x 1] x))"
# test_code = "(let [x 32] (+ (let [x 10] x) x))"
# test_code = "(let [x (let [x 4] (+ x 1))] (+ x 2))"
# test flatten
# test_code = "(+ 15 (+ 1 2))" 
# test_code = "(let [x (+ 15 (+ 1 2))] (+ x 41))"
test_code = "(let [a 42] (let [b a] a))"

scanner = scan(test_code)
print("[Scan list]")
print(scanner.lst)

ast = parse(scanner)
print("\n[Ast]")
print(ast)

unify_ast = uniquify(ast, None)
print("\n[Unify]")
print(unify_ast)

flatten = Flatten(unify_ast)
flatten.run()
print("\n[Flatten]")
print_op_lst(flatten.op_lst)

op_lst = select_instruction(flatten.op_lst)
print("\n[Select instruction]")
print_op_lst(op_lst)

op_lst_with_home = assign_home(op_lst)
print("\n[Assign home]")
print_op_lst(op_lst_with_home)

op_lst_with_patch = patch_instuction(op_lst_with_home)
print("\n[Patch instruction]")
print_op_lst(op_lst_with_patch)

print("\n[Print X86-64 code]")
print_x84_64(op_lst_with_patch)
