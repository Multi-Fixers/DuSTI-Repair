package Example;

class Account {
    int balance;

    public Account(int initialBalance) { // Line 3
        balance = initialBalance; // Line 4
    }

    public void deposit(int amount) { // Line 6
        balance += amount; // Line 7
    }

    public int getBalance() { // Line 9
        return balance; // Line 10
    }
}

public class BankApp {
    public static void main(String[] args) {
        Account acc = new Account(100); // Line 14
        acc.deposit(50); // Line 15
        System.out.println(acc.getBalance()); // Line 16
    }
}

