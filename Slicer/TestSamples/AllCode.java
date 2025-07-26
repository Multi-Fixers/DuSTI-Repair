import java.util.Scanner;

public class AllCode {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        
        // Example 1: Absolute difference between two integers
        System.out.print("Enter two integers for difference calculation: ");
        int num1 = scanner.nextInt();
        int num2 = scanner.nextInt();
        int difference = num1 - num2;
        System.out.println("Absolute difference: " + Math.abs(difference));
        
        // Example 2: Find the absolute value of elements in an array
        int[] numbers = {-5, 10, -15, 20, -25};
        System.out.println("\nAbsolute values of array elements:");
        for (int i = 0; i < numbers.length; i++) {
            System.out.println("Original: " + numbers[i] + ", Absolute: " + Math.abs(numbers[i]));
        }
        
        // Example 3: Check if the absolute difference is within a threshold
        System.out.print("\nEnter two integers to check threshold: ");
        int value1 = scanner.nextInt();
        int value2 = scanner.nextInt();
        int threshold = 10;
        int value3 = Math.abs(value1 - value2);
        int value4 = Math.abs(3-6);
        if (value3 <= threshold) {
            int value5 = Math.abs(value1 -19);
            System.out.println(value1);
        } else {
            System.out.println("The difference exceeds the threshold of " + threshold);
        }
        System.out.println(value1);
        // Example 4: Calculate absolute sum of multiple integers
        System.out.print("\nEnter three integers for absolute sum calculation: ");
        int a = scanner.nextInt();
        int b = scanner.nextInt();
        int c = scanner.nextInt();
        int absSum = Math.abs(a) + Math.abs(b) + Math.abs(c);
        System.out.println("Sum of absolute values: " + absSum);
        
        scanner.close();
    }
}
