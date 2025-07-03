def run_prog_message_output(prog: list[str]):
    """Run a program and return its output

    Parameters
    ----------
    prog : list[str]
        The program to run, prog[0] should be the binary name, findable by shutil.which

    Returns
    -------
    message: str
        None if the program ran successfully, or a message indicating what went wrong
    output: str
        The standard output of the program
    """
    from shutil import which
    from subprocess import run
    message, output = None, None
    if which(prog[0]):
        res = run(prog, capture_output=True, text=True)
        output = res.stdout
        if res.returncode or len(res.stderr):
            message = f'Evaluating "{" ".join(prog)}" produced error: {res.stderr}'
    else:
        message = f'{prog[0]} not found'

    return message, output