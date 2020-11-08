# TODO uniquify
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
            if i < length:
                letter = code_str[i]
                while "0" <= letter <= "9":
                    num = num * 10 + int(letter)
                    i = i + 1
                    letter = code_str[i]
            lst.append(num)
        elif "a" <= letter <= "z" or "A" <= letter <= "Z":
            tmp = letter
            if i < length:
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
    lvldict = {}

    def __init__(self, old_env, key, lvl):
        self.old_env = old_env
        self.key = key
        self.lvl = lvl

    @staticmethod
    def get_new_lvl(var):
        if var not in UniEnv.lvldict:
            UniEnv.lvldict[var] = 1
        else:
            UniEnv.lvldict[var] += 1
        return UniEnv.lvldict[var]


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
        lvl = UniEnv.get_new_lvl(exp.var)
        env = UniEnv(env, exp.var, lvl)
        new_var = exp.var + "." + str(lvl)
        return LetExp(new_var, new_let_exp, uniquify(exp.body_exp, env))
    elif exp_type == AddExp:
        exp1 = uniquify(exp.exp1, env)
        exp2 = uniquify(exp.exp2, env)
        return AddExp(exp1, exp2)


class Flattern:
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
            tmp = "tmp." + str(UniEnv.get_new_lvl("tmp"))
            self.op_lst.append(("assign", tmp, final_exp))
            self.op_lst.append(("return", tmp))


def select_instruction(op_lst):
    res = []
    for op in op_lst:
        if op[0] == "assign":
            var = op[2]
            if type(var) not in (int, str):
                if type(var[1]) == int:
                    res.append(("movq", ("int", var[1]), ("var", op[1])))
                    if type(var[2]) == int:
                        res.append(("addq", ("int", var[2]), ("var", op[1])))
                    elif type(var[2]) == str:
                        res.append(("addq", ("var", var[2]), ("var", op[1])))
                elif type(var[1]) == str:
                    res.append(("movq", ("var", var[1]), ("var", op[1])))
                    if type(var[2]) == int:
                        res.append(("addq", ("int", var[2]), ("var", op[1])))
                    elif type(var[2]) == str:
                        res.append(("addq", ("var", var[2]), ("var", op[1])))
            elif type(var) == int:
                res.append(("movq", ("int", var), ("var", op[1])))
            elif type(var) == str:
                res.append(("movq", ("var", var), ("var", op[1])))
        elif op[0] == "return":
            if type(op[1]) == int:
                res.append(("movq", ("int", op[1]), ('reg', 'rax')))
            if type(op[1]) == str:
                res.append(("movq", ("var", op[1]), ('reg', 'rax')))
    return res


home_dict = {}
level = 1


def get_home_dict(var):
    global level
    if var not in home_dict:
        offset = -8 * level
        home_dict[var] = offset
        level = level + 1
        return offset
    else:
        return home_dict[var]


def assign_home(op_lst):
    res = []
    for op in op_lst:
        if op[1][0] == "var":
            offset = get_home_dict(op[1][1])
            tmp1 = ("deref", "rbp", offset)
        else:
            tmp1 = op[1]
        if op[2][0] == "var":
            offset = get_home_dict(op[2][1])
            tmp2 = ("deref", "rbp", offset)
        else:
            tmp2 = op[2]

        res.append((op[0], tmp1, tmp2))
    return res


def patch_instruction(op_lst):
    res = []
    for op in op_lst:
        if op[0] == "movq":
            if op[1][0] == "deref" and op[2][0] == "deref":
                res.append(("movq", op[1], ("reg", "rax")))
                res.append(("movq", ("reg", "rax"), op[2]))
            else:
                res.append(op)
        elif op[0] == "addq":
            if op[1][0] == "deref" and op[2][0] == "deref":
                res.append(("movq", op[1], ("reg", "rax")))
                res.append(("addq", ("reg", "rax"), op[2]))
            else:
                res.append(op)
    return res


def trans_operand_to_str(op):
    if op[0] == "int":
        return "$" + str(op[1])
    elif op[0] == "deref":
        return str(op[2]) + "(%" + str(op[1]) + ")"
    elif op[0] == "reg":
        return "%" + str(op[1])


def print_x86_64(op_lst):
    print("    .global main")
    print("main:")
    print("    pushq %rbp")
    print("    movq %rsp, %rbp")
    tmp = int(level / 2)
    print("    subq $" + str(tmp * 16) + ", %rsp")

    for op in op_lst:
        print("    " + str(op[0]) + " " + str(trans_operand_to_str(op[1])) + ", " + str(trans_operand_to_str(op[2])))

    print("    add $" + str(tmp * 16) + ", %rsp")
    print("    popq %rbp")
    print("    retq")


# test_code = "(+ (let [x 1] x) (let [x 1] x))"
# test_code = "(let [x 32] (+ (let [x 10] x) x))"
# test_code = "(let [x (let [x 4] (+ x 1))] (+ x 2))"
# "(let ([x.1 32]) " \        [(x,1)]           (none, x, 1)
# "   (+ (let ([x.2 10]) " \  [(x,1), [x,2]]    ((none, x, 1) , x, 2)
# "               x.2)" \     [(x,1), [x,2]]    ((none, x, 1) , x, 2)
# "      x.2))"               [(x,1), [x,2]]    (none, x, 1)
# test_code = "1"
# test_code = "(let [x 1] 1)"
# test_code = "(+ 3 (let [x 1] x))"
# test_code = "(+ (let [x 1] x) (let [x 1] x))"
# test_code = "(let [x 32] (+ (let [x 10] x) x))"
# test_code = "(let [x (let [x 4] (+ x 1))] (+ x 2))"
# test flatten
# test_code = "(+ 15 (+ 1 2))"
#test_code = "(let [x (+ 15 (+ 1 2))] (+ x 41))"
test_code = "(let [a 42] (let [b a] a))"
a = scan(test_code)
print(a.lst)
b = parse(a)
print(b)
uExp = uniquify(b, None)
print(uExp)

print("\nFlattern")
f = Flattern(uExp)
f.run()
print_op_lst(f.op_lst)

print("\nselect_instruction")
si = select_instruction(f.op_lst)
print_op_lst(si)

print("\nassign_home")
ah = assign_home(si)
print_op_lst(ah)

print("\npatch_instruction")
pi = patch_instruction(ah)
print_op_lst(pi)

print("\nprint_x86_64")
print_x86_64(pi)
