import java.io.File;
import java.io.PrintStream;
import java.util.List;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

/**
 * Live oracle probe: report the /ByteRange byte-offset arithmetic of a signed
 * PDF exactly as Apache PDFBox parses it, plus independent invariants derived
 * from the raw file bytes.
 *
 * The whole point of the external-signing byte-range computation is that the
 * four integers [a b c d] must satisfy, byte-for-byte:
 *   a == 0
 *   b == offset of the byte AFTER the `<` opening the /Contents hex string
 *        (i.e. the gap [b, c) is exactly `<HEX...>` minus its delimiters? No —
 *        per ISO 32000-1 the excluded span is the bytes between < and >,
 *        exclusive of the delimiters; PDFBox brackets so range1 ends just
 *        after `<` and range2 starts at `>`).
 *   c == position of the `>` closing the /Contents string
 *   d == fileLength - c   (range2 runs to EOF)
 *   a + b ... no overlap; b < c; c + d == fileLength
 *
 * This probe emits PDFBox's parsed ByteRange and the file-derived ground truth
 * so the python side can assert pypdfbox's own get_byte_range()/extract match
 * BOTH PDFBox's parse AND the raw-byte ground truth.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ByteRangeProbe signed.pdf
 * Output (stdout, one key=value per line):
 *   count=<number of signature dicts>
 *   sig.0.byterange=a,b,c,d           (as PDFBox parses the COSArray)
 *   sig.0.fileLength=<raw file size in bytes>
 *   sig.0.contentsOpen=<index of `<` delimiting /Contents>     (file-derived)
 *   sig.0.contentsClose=<index of matching `>`>                (file-derived)
 *   sig.0.signedContentLength=<getSignedContent(fileBytes).length>
 *   sig.0.coversWholeFileExceptContents=<true|false>
 *   sig.0.byteRangeMatchesContents=<true|false>
 */
public final class ByteRangeProbe {

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
                out.println(prefix + "fileLength=" + fileBytes.length);

                // getSignedContent stitches together the two bracketed slices.
                byte[] signedContent = sig.getSignedContent(fileBytes);
                out.println(prefix + "signedContentLength=" + signedContent.length);

                // Derive the /Contents `<...>` span from the raw bytes around
                // the gap PDFBox's ByteRange leaves. ByteRange is [a b c d];
                // the excluded region is [b, c). The byte at b-1 should be the
                // `<` opening delimiter (range1 includes it) and the byte at c
                // should be the `>` closing delimiter (range2 includes it).
                int a = br[0];
                int b = br[1];
                int c = br[2];
                int d = br[3];

                int contentsOpen = a + b - 1;       // index of `<`
                int contentsClose = c;              // index of `>`
                out.println(prefix + "contentsOpen=" + contentsOpen);
                out.println(prefix + "contentsClose=" + contentsClose);

                boolean openIsBracket =
                        contentsOpen >= 0
                        && contentsOpen < fileBytes.length
                        && fileBytes[contentsOpen] == '<';
                boolean closeIsBracket =
                        contentsClose >= 0
                        && contentsClose < fileBytes.length
                        && fileBytes[contentsClose] == '>';

                // Range covers the entire file except the bytes strictly
                // between the delimiters: a==0, c+d==fileLength, b<c.
                boolean coversWholeFile =
                        a == 0
                        && (c + d) == fileBytes.length
                        && b < c
                        && (signedContent.length == (b + d));
                out.println(prefix + "coversWholeFileExceptContents="
                        + coversWholeFile);

                out.println(prefix + "byteRangeMatchesContents="
                        + (openIsBracket && closeIsBracket));
                i++;
            }
        }
    }
}
