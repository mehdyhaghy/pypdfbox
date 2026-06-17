import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/** Differential malformed-geometry probe for PDFBox Predictor (wave 1518). */
public final class PredictorDecodeParamsFuzzProbe {
    private static final Method ROW_LENGTH;
    private static final Method DECODE_ROW;

    static {
        try {
            Class<?> cls = Class.forName("org.apache.pdfbox.filter.Predictor");
            ROW_LENGTH = cls.getDeclaredMethod(
                    "calculateRowLength", int.class, int.class, int.class);
            DECODE_ROW = cls.getDeclaredMethod(
                    "decodePredictorRow", int.class, int.class, int.class,
                    int.class, byte[].class, byte[].class);
            ROW_LENGTH.setAccessible(true);
            DECODE_ROW.setAccessible(true);
        } catch (Exception e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xf, 16));
            sb.append(Character.forDigit(b & 0xf, 16));
        }
        return sb.toString();
    }

    private static String error(Throwable e) {
        Throwable cause = e instanceof InvocationTargetException ? e.getCause() : e;
        return cause.getClass().getSimpleName();
    }

    private static void rowLength(String name, int colors, int bpc, int columns) {
        try {
            int value = (Integer) ROW_LENGTH.invoke(null, colors, bpc, columns);
            System.out.println("CASE " + name + " value=" + value);
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + error(e));
        }
    }

    private static void decode(String name, int predictor, int colors, int bpc,
            int columns, byte[] row, byte[] previous) {
        try {
            DECODE_ROW.invoke(null, predictor, colors, bpc, columns, row, previous);
            System.out.println("CASE " + name + " row=" + hex(row));
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + error(e));
        }
    }

    public static void main(String[] args) {
        rowLength("row_normal", 3, 8, 5);
        rowLength("row_subbyte", 1, 1, 9);
        rowLength("row_zero_columns", 1, 8, 0);
        rowLength("row_negative_columns", 1, 8, -1);
        rowLength("row_zero_colors", 0, 8, 4);
        rowLength("row_negative_bpc", 1, -8, 4);
        rowLength("row_overflow", 32, 32, Integer.MAX_VALUE);

        decode("none", 1, 0, 0, 0, new byte[] {1, 2, 3}, new byte[0]);
        decode("unknown", 99, 1, 8, 3, new byte[] {1, 2, 3}, new byte[3]);
        decode("png_sub", 11, 1, 8, 4, new byte[] {1, 2, 3, 4}, new byte[4]);
        decode("png_up_short_prev", 12, 1, 8, 4,
                new byte[] {1, 2, 3, 4}, new byte[] {9});
        decode("png_avg", 13, 1, 8, 4,
                new byte[] {1, 2, 3, 4}, new byte[] {8, 7, 6, 5});
        decode("png_paeth", 14, 1, 8, 4,
                new byte[] {1, 2, 3, 4}, new byte[] {8, 7, 6, 5});
        decode("tiff_1bit", 2, 1, 1, 9,
                new byte[] {(byte) 0x93, (byte) 0x80}, new byte[2]);
        decode("empty_invalid_geometry", 12, 0, 0, 0, new byte[0], new byte[0]);
    }
}
