package Example;

public class LoopExample {
    private static int counter = 0;

    public static void extra(int counter){
        counter += 1;
        System.out.println("extra");
    }
    public static void main(String[] args) {
        int sum = 0;              // Line 3
        for (int i = 1; i <= 5; i++) { // Line 4
            sum += i;             // Line 5
        }
        if (sum > 10) {           // Line 6
            System.out.println("Sum is large"); // Line 7
        }

        extra(counter);
    }
}

