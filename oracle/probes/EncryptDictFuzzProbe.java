import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.SecurityHandler;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Differential fuzz probe for {@code /Encrypt}-dictionary construction +
 * decryption-bootstrap leniency, Apache PDFBox 3.0.7 (wave 1511, agent C).
 *
 * Complements the existing well-formed encryption oracle suite (crypt-filter
 * routing, /EncryptMetadata, AES-256 R6 /Perms validation, /StmF /StrF
 * defaults) — none of which exercise the MALFORMED /Encrypt dict subset this
 * probe targets: missing / unknown /Filter, /V and /R sweeps and mismatches,
 * odd / mistyped /Length, missing or mistyped /O /U /OE /UE /Perms, missing
 * /P, /P as a real, missing /CF for V4/V6, unknown /CFM, /EncryptMetadata
 * variants, and empty-user-password validation against a mutated /U.
 *
 * Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/encryption/oracle/test_encrypt_dict_fuzz_wave1511.py) writes
 * the deterministic corpus of mutated-/Encrypt PDFs into a directory plus a
 * {@code manifest.txt} (one case name per line, in order); this probe loads
 * each {@code <case>.pdf} with an EMPTY password via {@code Loader.loadPDF}
 * and reports a stable framed line. Both sides read the exact same bytes on
 * disk, so the open contract is directly comparable.
 *
 * Line grammar (one per case, manifest order):
 *   CASE &lt;name&gt; open=&lt;ERR:&lt;ExcSimpleName&gt; | ok enc=&lt;0|1&gt; handler=&lt;HandlerSimpleName-or-null&gt; keybits=&lt;n-or-?&gt; text=&lt;sample-or-NOTEXT&gt;&gt;
 *
 * "open=ERR:&lt;X&gt;" means {@code Loader.loadPDF(file, "")} threw exception
 * class X. On success: enc = isEncrypted; handler = the security-handler
 * simple class name resolved from the /Encrypt dict (or "null"); keybits =
 * the handler's key length in bits (or "?" if unavailable); text = the first
 * non-blank line of extracted text (the encrypted marker, decrypted) or
 * "NOTEXT" when extraction yields nothing.
 */
public final class EncryptDictFuzzProbe {

    static PrintStream out;

    static String handlerName(PDDocument doc) {
        try {
            PDEncryption enc = doc.getEncryption();
            if (enc == null) {
                return "null";
            }
            SecurityHandler<?> sh = enc.getSecurityHandler();
            return sh == null ? "null" : sh.getClass().getSimpleName();
        } catch (Exception e) {
            return "null";
        }
    }

    static String keyBits(PDDocument doc) {
        try {
            PDEncryption enc = doc.getEncryption();
            if (enc == null) {
                return "?";
            }
            SecurityHandler<?> sh = enc.getSecurityHandler();
            if (sh == null) {
                return "?";
            }
            int kb = sh.getKeyLength();
            return Integer.toString(kb);
        } catch (Exception e) {
            return "?";
        }
    }

    static String textSample(PDDocument doc) {
        try {
            String t = new PDFTextStripper().getText(doc);
            if (t == null) {
                return "NOTEXT";
            }
            for (String line : t.split("\n")) {
                String s = line.trim();
                if (!s.isEmpty()) {
                    return s;
                }
            }
            return "NOTEXT";
        } catch (Exception e) {
            return "NOTEXT";
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf, "");
            String handler = handlerName(doc);
            String kb = keyBits(doc);
            String text = textSample(doc);
            sb.append("open=ok enc=").append(doc.isEncrypted() ? "1" : "0");
            sb.append(" handler=").append(handler);
            sb.append(" keybits=").append(kb);
            sb.append(" text=").append(text);
        } catch (Exception e) {
            sb.append("open=ERR:").append(e.getClass().getSimpleName());
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
