import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.pdmodel.encryption.PDCryptFilterDictionary;

/**
 * Live oracle probe: emit the {@code PDCryptFilterDictionary} default-value
 * surface for an empty (newly-constructed) crypt-filter dictionary.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CryptFilterDictDefaultProbe
 *
 * PDFBox 3.0.7 {@code PDCryptFilterDictionary.getLength()} returns
 * {@code getInt(COSName.LENGTH, 40)} — the default is 40 (length in BITS, a
 * multiple of 8 per the Javadoc), NOT 5 bytes. This probe pins that default so
 * pypdfbox's {@code get_length()} can be asserted line-for-line.
 *
 * Output (UTF-8, stdout):
 *   defaultLength=<int>
 *   defaultEncryptMetadata=<true|false>
 *   afterSet8Length=<int>
 */
public final class CryptFilterDictDefaultProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        PDCryptFilterDictionary cf = new PDCryptFilterDictionary(new COSDictionary());
        out.println("defaultLength=" + cf.getLength());
        out.println("defaultEncryptMetadata=" + cf.isEncryptMetaData());
        cf.setLength(8);
        out.println("afterSet8Length=" + cf.getLength());
    }
}
