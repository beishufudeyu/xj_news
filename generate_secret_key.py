import os
import base64


def generate(length=48):
    key = os.urandom(length)
    secret_key = base64.b64encode(key)
    print(secret_key)
    return secret_key


if __name__ == "__main__":
    generate()
