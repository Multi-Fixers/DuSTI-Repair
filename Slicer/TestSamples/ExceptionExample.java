package Example;

public class ExceptionExample {
    public static void main(String[] args) {
        try {
            int[] numbers = {1, 2, 3}; // Line 3
            int result = numbers[5];  // Line 4
            System.out.println(result); // Line 5
        } catch (ArrayIndexOutOfBoundsException e) { // Line 6
            System.out.println("Index out of bounds"); // Line 7
        }
    }
}
