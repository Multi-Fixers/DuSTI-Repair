package Example;

public class Example {
    public void example(){
        System.out.println("hello");
    }
    public static void main(String[] args) {
        int sum = 0;
        int prod = 0;
        int i;
        int n = 10;
        for (i = 0; i < 10; i++) {
            sum += 1;
            prod += n;
        }
        System.out.println(sum);
        System.out.println(prod);
    }
}
