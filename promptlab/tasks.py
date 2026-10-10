from __future__ import annotations

PRESET_TASKS = {
    "Palindrome checker": {
        "name": "Palindrome checker",
        "description": ("Implement is_palindrome(text). Return True when text reads the same forwards and backwards after "
                        "converting to lowercase and removing all non-alphanumeric characters. Otherwise return False. "
                        "An empty or punctuation-only string is considered a palindrome."),
        "function_name": "is_palindrome",
        "signature": "def is_palindrome(text: str) -> bool",
        "tests": [
            {"args": ["racecar"], "expected": True},
            {"args": ["A man, a plan, a canal: Panama!"], "expected": True},
            {"args": ["hello"], "expected": False},
            {"args": [""], "expected": True},
            {"args": ["..."], "expected": True},
            {"args": ["Was it a car or a cat I saw?"], "expected": True},
        ],
    },
    "Prime number checker": {
        "name": "Prime number checker",
        "description": ("Implement is_prime(n). Return True if integer n is a prime number and False otherwise. "
                        "Numbers less than 2 are not prime. Avoid unnecessarily slow trial division."),
        "function_name": "is_prime",
        "signature": "def is_prime(n: int) -> bool",
        "tests": [
            {"args": [-5], "expected": False}, {"args": [0], "expected": False},
            {"args": [1], "expected": False}, {"args": [2], "expected": True},
            {"args": [3], "expected": True}, {"args": [9], "expected": False},
            {"args": [17], "expected": True}, {"args": [97], "expected": True},
        ],
    },
    "Count vowels": {
        "name": "Count vowels",
        "description": ("Implement count_vowels(text). Return the number of English vowels (a, e, i, o, u) in the input string, "
                        "case-insensitively. Do not count y as a vowel."),
        "function_name": "count_vowels",
        "signature": "def count_vowels(text: str) -> int",
        "tests": [
            {"args": ["hello"], "expected": 2}, {"args": ["AEIOU"], "expected": 5},
            {"args": ["rhythm"], "expected": 0}, {"args": [""], "expected": 0},
            {"args": ["Data Science"], "expected": 5},
        ],
    },
    "FizzBuzz": {
        "name": "FizzBuzz",
        "description": ("Implement fizz_buzz(n). Return a list of strings for integers from 1 through n inclusive. "
                        "Use 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for multiples of both, "
                        "and the decimal number string otherwise. If n is less than 1, return an empty list."),
        "function_name": "fizz_buzz",
        "signature": "def fizz_buzz(n: int) -> list[str]",
        "tests": [
            {"args": [0], "expected": []}, {"args": [-2], "expected": []},
            {"args": [1], "expected": ["1"]},
            {"args": [3], "expected": ["1", "2", "Fizz"]},
            {"args": [5], "expected": ["1", "2", "Fizz", "4", "Buzz"]},
            {"args": [15], "expected": ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]},
        ],
    },
}
