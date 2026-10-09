def ask_int(prompt: str, min_val: int = None, max_val: int = None) -> int:
    while True:
        try:
            val = int(input(prompt))
            if (min_val is not None and val < min_val) or (max_val is not None and val > max_val):
                print(f"Digite um número entre {min_val} e {max_val}.")
                continue
            return val
        except ValueError:
            print("Entrada inválida, digite um número inteiro.")

def ask_str(prompt: str, valid_options: list = None) -> str:
    while True:
        val = input(prompt).strip()
        if valid_options and val not in valid_options:
            print(f"Opções válidas: {valid_options}")
            continue
        return val

def ask_yes_no(prompt: str) -> bool:
    while True:
        resp = input(f"{prompt} (s/n): ").strip().lower()
        if resp in ["s", "sim"]:
            return True
        elif resp in ["n", "não", "nao"]:
            return False
        else:
            print("Responda com 's' ou 'n'.")
