def greet(name):
    """Say hello."""
    greeting = f"hello, {name}!"
    print(greeting.title())


def main():
    for who in ["ada", "grace", "linus", "margaret"]:
        greet(who)


if __name__ == "__main__":
    main()
