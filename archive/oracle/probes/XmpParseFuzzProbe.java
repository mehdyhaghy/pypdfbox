import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.List;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.XMPSchema;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.xml.DomXmpParser;
import org.apache.xmpbox.xml.XmpParsingException;

/**
 * Differential parse-leniency fuzz probe for Apache xmpbox
 * {@code DomXmpParser.parse(byte[])}, PDFBox/xmpbox 3.0.7 (wave 1512, agent D).
 *
 * Drives a fixed, seed-free corpus of malformed / edge-case raw XMP packets and
 * reports, per case, the parser's strictness contract: either the
 * {@code XmpParsingException} {@code ErrorType} when parse throws, or a stable
 * shape dump of what survived parsing — the set of registered schemas (by
 * namespace + prefix), each schema's property count and the sorted local names
 * of its top-level properties. Both the strict (upstream default) and the
 * lenient ({@code setStrictParsing(false)}) arm are exercised per case.
 *
 * The corpus is supplied by the pypdfbox sibling test as a single input file
 * (so the exact same bytes drive both sides). File grammar — one case per line:
 *   {@code <name> \t <base64-of-packet-bytes> \t <strict|lenient>}
 * Blank lines and lines starting with {@code #} are ignored.
 *
 * Output grammar — exactly one line per case, in input order:
 *   {@code CASE <name> EXC <ErrorType>}                       (parse threw)
 *   {@code CASE <name> OK <schemaToken>;<schemaToken>;...}    (parse succeeded)
 * where each {@code schemaToken} is
 *   {@code <prefix>|<namespace>|<propCount>|<localName,localName,...>}
 * Schemas are sorted by namespace then prefix; property local names are sorted.
 * {@code OK -} means parse succeeded with zero schemas. An unexpected
 * (non-XmpParsingException) throwable is reported as {@code EXC OTHER:<class>}.
 *
 * The pypdfbox sibling (tests/xmpbox/oracle/test_xmp_parse_fuzz_wave1512.py)
 * rebuilds the identical corpus, emits the identical grammar from
 * pypdfbox.xmpbox.DomXmpParser, and asserts line-for-line parity. Intentional
 * robustness divergences are pinned both-sides there with a CHANGES.md
 * citation.
 */
public final class XmpParseFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        List<String> lines = Files.readAllLines(
                Paths.get(args[0]), StandardCharsets.UTF_8);
        for (String line : lines) {
            if (line.isEmpty() || line.charAt(0) == '#') {
                continue;
            }
            String[] parts = line.split("\t", -1);
            String name = parts[0];
            byte[] packet = Base64.getDecoder().decode(parts[1]);
            boolean strict = !"lenient".equals(parts[2]);
            out.println("CASE " + name + " " + run(packet, strict));
        }
    }

    private static String run(byte[] packet, boolean strict) {
        DomXmpParser parser;
        try {
            parser = new DomXmpParser();
        } catch (XmpParsingException e) {
            return "EXC " + e.getErrorType().name();
        }
        parser.setStrictParsing(strict);
        XMPMetadata meta;
        try {
            meta = parser.parse(packet);
        } catch (XmpParsingException e) {
            return "EXC " + e.getErrorType().name();
        } catch (Throwable t) {
            return "EXC OTHER:" + t.getClass().getSimpleName();
        }
        return "OK " + shape(meta);
    }

    private static String shape(XMPMetadata meta) {
        List<XMPSchema> schemas = meta.getAllSchemas();
        if (schemas == null || schemas.isEmpty()) {
            return "-";
        }
        List<String> tokens = new ArrayList<>();
        for (XMPSchema s : schemas) {
            List<String> names = new ArrayList<>();
            for (AbstractField f : s.getAllProperties()) {
                names.add(f.getPropertyName());
            }
            Collections.sort(names);
            tokens.add(s.getPrefix() + "|" + s.getNamespace() + "|"
                    + names.size() + "|" + String.join(",", names));
        }
        Collections.sort(tokens);
        return String.join(";", tokens);
    }
}
