package Example;

class MathUtils {
    public static int square(int x) { // Line 3
        return x * x; // Line 4
    }
}

public class NestedCalls {
    public static void main(String[] args) {
        int result = MathUtils.square(5); // Line 8
        System.out.println(result); // Line 9
    }
}
