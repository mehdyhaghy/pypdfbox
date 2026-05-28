import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.nio.file.Files;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;

/**
 * Live oracle probe for Apache PDFBox's PNG/TIFF predictor transform, isolated
 * from the (de)compression stage so we can compare the predictor bytes
 * byte-for-byte — especially for sub-byte component widths (BitsPerComponent
 * 1/2/4) where the sample bit-packing and the handling of trailing padding
 * bits in a non-byte-aligned row is the divergence point.
 *
 * Usage:
 *   java -cp ... PredictorProbe raw.bin Predictor=2,Columns=13,Colors=1,BitsPerComponent=1
 *
 *   args[0] - path to a file holding the RAW (pre-predictor) row bytes.
 *   args[1] - comma-separated integer params; must include Predictor and the
 *             geometry (Columns/Colors/BitsPerComponent). Defaults mirror
 *             PDFBox: Colors=1, BitsPerComponent=8, Columns=1.
 *
 * It feeds the raw bytes through {@code Predictor.wrapPredictor} (the same
 * PredictorOutputStream PDFBox uses on encode) and writes the predicted bytes
 * to stdout verbatim. {@code wrapPredictor} is package-private in PDFBox, so
 * we reach it via reflection.
 */
public final class PredictorProbe {
    public static void main(String[] args) throws Exception {
        byte[] raw = Files.readAllBytes(new File(args[0]).toPath());

        COSDictionary params = new COSDictionary();
        for (String pair : args[1].split(",")) {
            int eq = pair.indexOf('=');
            if (eq < 0) {
                continue;
            }
            String key = pair.substring(0, eq).trim();
            long value = Long.parseLong(pair.substring(eq + 1).trim());
            params.setItem(COSName.getPDFName(key), COSInteger.get(value));
        }

        ByteArrayOutputStream predicted = new ByteArrayOutputStream();
        Class<?> predictorClass = Class.forName("org.apache.pdfbox.filter.Predictor");
        Method wrap = predictorClass.getDeclaredMethod(
                "wrapPredictor", OutputStream.class, COSDictionary.class);
        wrap.setAccessible(true);
        OutputStream wrapped = (OutputStream) wrap.invoke(null, predicted, params);
        wrapped.write(raw);
        wrapped.flush();
        wrapped.close();

        OutputStream out = System.out;
        out.write(predicted.toByteArray());
        out.flush();
    }
}
