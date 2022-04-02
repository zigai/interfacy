def func_1(a: str, b: int, c: set, d=5, e: bool = False):
    print(a, b, c, d, e)


from cliera import Cliera

Cliera.run(func_1)