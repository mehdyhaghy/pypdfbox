import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDMetadata;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Differential fuzz probe for the crypt-filter DECODE / DISPATCH path, Apache
 * PDFBox 3.0.7 (wave 1517, agent D).
 *
 * Complements {@code EncryptDictFuzzProbe} (which fuzzes the /Encrypt-dict
 * PARSE + decryption-bootstrap leniency) and the well-formed crypt-filter
 * oracle suite (CryptFilterProbe / CryptRoutingProbe — routing + introspection
 * of valid /StdCF docs). NONE of those exercise the actual string/stream
 * decryption DISPATCH under malformed / unusual crypt-filter configs:
 *
 *   - an unknown /CFM (e.g. /Zz) on the default crypt filter,
 *   - /CFM /None (the spec "no cipher" value),
 *   - a /Type /Metadata stream whose body is cleartext (&lt;?xpacket) while
 *     /EncryptMetadata is true (PDFBOX-3173 / PDFBOX-2603 heuristic),
 *   - /StmF / /StrF pointing at a filter absent from /CF,
 *   - per-slot Identity routing variants.
 *
 * File-based: the pypdfbox companion test authors a deterministic corpus of
 * encrypted PDFs into a directory plus a {@code manifest.txt} (one case name
 * per line, in order); this probe loads each {@code &lt;case&gt;.pdf} with an
 * EMPTY user password via {@code Loader.loadPDF(file, "")} and reports a stable
 * framed line per case. Both sides read the exact same bytes on disk so the
 * decode contract is directly comparable.
 *
 * Line grammar (one per case, manifest order):
 *   CASE &lt;name&gt; open=&lt;ok|ERR:&lt;ExcSimpleName&gt;&gt; text=&lt;sample|NOTEXT&gt; meta=&lt;sample|NOMETA|ERR&gt;
 *
 * - open=ERR:&lt;X&gt; means {@code Loader.loadPDF(file, "")} threw class X.
 * - text = first non-blank line of extracted text, whitespace-collapsed, or
 *   NOTEXT when extraction yields nothing.
 * - meta = whitespace-collapsed document metadata stream, or NOMETA when the
 *   catalog has no /Metadata, or ERR when reading it threw.
 */
public final class CryptFilterFuzzProbe {

    static String sampleText(PDDocument doc) {
        try {
            String t = new PDFTextStripper().getText(doc);
            if (t == null) {
                return "NOTEXT";
            }
            for (String line : t.split("\n")) {
                String s = line.trim().replaceAll("\\s+", " ");
                if (!s.isEmpty()) {
                    return s;
                }
            }
            return "NOTEXT";
        } catch (Exception e) {
            return "ERR";
        }
    }

    static String sampleMeta(PDDocument doc) {
        try {
            PDMetadata md = doc.getDocumentCatalog().getMetadata();
            if (md == null) {
                return "NOMETA";
            }
            byte[] b = md.toByteArray();
            String s = new String(b, "ISO-8859-1").replaceAll("\\s+", " ").trim();
            return s.isEmpty() ? "NOMETA" : s;
        } catch (Exception e) {
            return "ERR";
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        for (String name : new String(
                java.nio.file.Files.readAllBytes(manifest.toPath()), "UTF-8")
                .split("\\R")) {
            String caseName = name.trim();
            if (caseName.isEmpty()) {
                continue;
            }
            File pdf = new File(dir, caseName + ".pdf");
            String openState;
            String text = "NOTEXT";
            String meta = "NOMETA";
            try (PDDocument doc = Loader.loadPDF(pdf, "")) {
                openState = "ok";
                text = sampleText(doc);
                meta = sampleMeta(doc);
            } catch (Exception e) {
                openState = "ERR:" + e.getClass().getSimpleName();
            }
            out.println(
                    "CASE " + caseName
                    + " open=" + openState
                    + " text=" + text
                    + " meta=" + meta);
        }
        // Touch otherwise-unused imports so the probe compiles cleanly under
        // -Werror-style toolchains and future maintainers see the intent.
        if (false) {
            COSBase b = COSName.IDENTITY;
            COSString s = new COSString("");
            AccessPermission ap = new AccessPermission();
            out.println(b + s.getString() + ap.canPrint());
        }
    }
}
