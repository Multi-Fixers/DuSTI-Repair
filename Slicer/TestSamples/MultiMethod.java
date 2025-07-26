package Example;

public class MultiMethod {
    public static void main(String[] args) {
        int a = 10; // Line 3
        int b = 20; // Line 4
        int result = calculate(a, b); // Line 5
        System.out.println(result); // Line 6
    }

    public static int calculate(int x, int y) { // Line 8
        return add(x, y); // Line 9
    }

    public static int add(int x, int y) { // Line 11
        return x + y; // Line 12
    }
}

