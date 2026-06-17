import java.io.File;
import java.io.PrintStream;
import java.util.List;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

/**
 * Live oracle probe: for an already-signed PDF on disk, report how Apache
 * PDFBox's two {@code getContents} overloads see the signature blob.
 *
 *   PDSignature.getContents()        — decodes the embedded /Contents
 *                                       COSString hex form to raw bytes.
 *   PDSignature.getContents(byte[])  — re-slices the blob OUT OF the raw file
 *                                       bytes using /ByteRange arithmetic
 *                                       (begin = br[0]+br[1]+1,
 *                                        len   = br[2]-begin-1) then
 *                                       hex-decodes via getConvertedContents.
 *
 * For a correctly-written signature the two MUST agree byte-for-byte. This is
 * the ground-truth check that pypdfbox's writer emits a /ByteRange whose
 * delimiter convention matches what upstream's getContents(byte[]) expects —
 * and equivalently that pypdfbox's reader (get_contents_from_bytes) uses the
 * same arithmetic.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SignatureContentsByteRangeProbe signed.pdf
 * Output (stdout, one key=value per line, per signature index i):
 *   count=<number of signature dicts>
 *   sig.i.byterange=a,b,c,d
 *   sig.i.cosStringHex=<getContents() as upper-hex>
 *   sig.i.byteRangeHex=<getContents(fileBytes) as upper-hex>
 *   sig.i.agree=<true|false>
 */
public final class SignatureContentsByteRangeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);
        byte[] fileBytes = java.nio.file.Files.readAllBytes(file.toPath());

        try (PDDocument doc = Loader.loadPDF(file)) {
            List<PDSignature> sigs = doc.getSignatureDictionaries();
            out.println("count=" + sigs.size());
            int i = 0;
            for (PDSignature sig : sigs) {
                String prefix = "sig." + i + ".";
                int[] br = sig.getByteRange();
                StringBuilder brSb = new StringBuilder();
                for (int j = 0; j < br.length; j++) {
                    if (j > 0) {
                        brSb.append(',');
                    }
                    brSb.append(br[j]);
                }
                out.println(prefix + "byterange=" + brSb);

                byte[] viaCosString = sig.getContents();
                byte[] viaByteRange = sig.getContents(fileBytes);
                out.println(prefix + "cosStringHex=" + hex(viaCosString));
                out.println(prefix + "byteRangeHex=" + hex(viaByteRange));
                out.println(prefix + "agree="
                        + java.util.Arrays.equals(viaCosString, viaByteRange));
                i++;
            }
        }
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(Character.forDigit((x >> 4) & 0xF, 16));
            sb.append(Character.forDigit(x & 0xF, 16));
        }
        return sb.toString().toUpperCase();
    }
}
