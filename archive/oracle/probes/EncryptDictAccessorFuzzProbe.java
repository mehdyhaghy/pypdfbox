import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;

/**
 * Differential fuzz probe for the {@code PDEncryption} dictionary accessors
 * ({@code /V /R /Length /P}) plus the {@code AccessPermission} factory /
 * byte-array surfaces, Apache PDFBox 3.0.7 (wave 1545, agent B).
 *
 * Distinct from the two adjacent probes:
 *   - {@code AccessPermissionFuzzProbe} (wave 1537) deep-fuzzes a single
 *     {@code new AccessPermission(int)} bit layout + the read-only lock.
 *   - {@code EncryptDictFuzzProbe} (wave 1511) is FILE-based: it writes mutated
 *     {@code /Encrypt} PDFs to disk and compares the open contract.
 *
 * This probe is IN-PROCESS and targets the decode layer those two skip: how the
 * {@code PDEncryption} integer accessors coerce a MALFORMED {@code /V /R
 * /Length /P} COS value (a float that truncates toward zero, a 64-bit int that
 * wraps to a Java 32-bit int, a wrong-typed name / bool / string that falls
 * back to the spec default), how the decoded {@code /P} flows into an
 * {@code AccessPermission}, and the factory + byte-array constructors
 * ({@code getOwnerAccessPermission}, no-arg, {@code AccessPermission(byte[])})
 * that wave 1537 never projected.
 *
 * Each invocation runs ONE named case (arg0) deterministically and prints a
 * stable {@code key=value} grammar, one per line, UTF-8.
 *
 * Cases:
 *   DICT &lt;name&gt;   — build an /Encrypt COSDictionary, emit V/R/Length/P plus
 *                       the AccessPermission(P) predicate matrix.
 *   AP &lt;name&gt;     — exercise an AccessPermission factory / byte[] ctor.
 *
 * The Python sibling
 * (tests/pdmodel/encryption/oracle/test_access_permission_fuzz_wave1545.py)
 * mirrors each line and asserts equality, pinning honest divergences in
 * comments (e.g. the short-byte[] exception class differs).
 */
public final class EncryptDictAccessorFuzzProbe {

    static PrintStream out;

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    private static COSDictionary dict(Object... kv) {
        COSDictionary d = new COSDictionary();
        for (int i = 0; i < kv.length; i += 2) {
            d.setItem((String) kv[i], (COSBase) kv[i + 1]);
        }
        return d;
    }

    private static void emitDict(COSDictionary d) {
        PDEncryption e = new PDEncryption(d);
        out.println("V=" + e.getVersion());
        out.println("R=" + e.getRevision());
        out.println("Length=" + e.getLength());
        int p = e.getPermissions();
        out.println("P=" + p);
        AccessPermission ap = new AccessPermission(p);
        out.println("bytes=" + ap.getPermissionBytes());
        out.println("canPrint=" + b(ap.canPrint()));
        out.println("canModify=" + b(ap.canModify()));
        out.println("canExtractContent=" + b(ap.canExtractContent()));
        out.println("canModifyAnnotations=" + b(ap.canModifyAnnotations()));
        out.println("canFillInForm=" + b(ap.canFillInForm()));
        out.println("canExtractForAccessibility=" + b(ap.canExtractForAccessibility()));
        out.println("canAssembleDocument=" + b(ap.canAssembleDocument()));
        out.println("canPrintFaithful=" + b(ap.canPrintFaithful()));
        out.println("isOwnerPermission=" + b(ap.isOwnerPermission()));
    }

    private static void runDict(String name) {
        switch (name) {
            case "empty":
                emitDict(dict());
                break;
            case "well_formed_r4":
                emitDict(dict("V", COSInteger.get(4), "R", COSInteger.get(4),
                        "Length", COSInteger.get(128), "P", COSInteger.get(-44)));
                break;
            case "p_all_clear":
                emitDict(dict("P", COSInteger.get(0)));
                break;
            case "p_all_set":
                emitDict(dict("P", COSInteger.get(-1)));
                break;
            case "p_default_minus4":
                emitDict(dict("P", COSInteger.get(-4)));
                break;
            case "p_only_print":
                emitDict(dict("P", COSInteger.get(4)));
                break;
            case "p_only_modify":
                emitDict(dict("P", COSInteger.get(8)));
                break;
            case "p_reserved_bits":
                emitDict(dict("P", COSInteger.get(3)));
                break;
            case "p_float_neg44":
                emitDict(dict("P", new COSFloat(-44.0f)));
                break;
            case "p_float_frac":
                emitDict(dict("P", new COSFloat(-3.9f)));
                break;
            case "p_float_pos_frac":
                emitDict(dict("P", new COSFloat(2052.8f)));
                break;
            case "p_huge_64bit":
                emitDict(dict("P", COSInteger.get(9999999999L)));
                break;
            case "p_name_wrongtype":
                emitDict(dict("P", COSName.getPDFName("foo")));
                break;
            case "p_bool_wrongtype":
                emitDict(dict("P", COSBoolean.TRUE));
                break;
            case "p_string_wrongtype":
                emitDict(dict("P", new COSString("123")));
                break;
            case "v_float":
                emitDict(dict("V", new COSFloat(4.0f)));
                break;
            case "v_name_wrongtype":
                emitDict(dict("V", COSName.getPDFName("Standard")));
                break;
            case "v_huge_64bit":
                emitDict(dict("V", COSInteger.get(9999999999L)));
                break;
            case "length_float":
                emitDict(dict("Length", new COSFloat(128.0f)));
                break;
            case "length_frac":
                emitDict(dict("Length", new COSFloat(127.6f)));
                break;
            case "length_zero":
                emitDict(dict("Length", COSInteger.get(0)));
                break;
            case "length_name_wrongtype":
                emitDict(dict("Length", COSName.getPDFName("128")));
                break;
            case "r_float":
                emitDict(dict("R", new COSFloat(6.0f)));
                break;
            case "r_huge_64bit":
                emitDict(dict("R", COSInteger.get(9999999999L)));
                break;
            case "r_string_wrongtype":
                emitDict(dict("R", new COSString("6")));
                break;
            case "all_wrongtype":
                emitDict(dict("V", COSName.getPDFName("x"), "R", COSBoolean.FALSE,
                        "Length", new COSString("y"), "P", COSName.getPDFName("z")));
                break;
            default:
                out.println("UNKNOWN_DICT=" + name);
        }
    }

    private static void emitAp(AccessPermission ap) {
        out.println("bytes=" + ap.getPermissionBytes());
        out.println("canPrint=" + b(ap.canPrint()));
        out.println("canModify=" + b(ap.canModify()));
        out.println("canExtractContent=" + b(ap.canExtractContent()));
        out.println("canAssembleDocument=" + b(ap.canAssembleDocument()));
        out.println("canPrintFaithful=" + b(ap.canPrintFaithful()));
        out.println("isOwnerPermission=" + b(ap.isOwnerPermission()));
    }

    private static void byteCtor(byte[] buf) {
        try {
            AccessPermission ap = new AccessPermission(buf);
            out.println("status=ok");
            emitAp(ap);
        } catch (Exception ex) {
            out.println("status=ERR:" + ex.getClass().getSimpleName());
        }
    }

    private static void runAp(String name) {
        switch (name) {
            case "owner_factory":
                emitAp(AccessPermission.getOwnerAccessPermission());
                break;
            case "no_arg":
                emitAp(new AccessPermission());
                break;
            case "byte_fffffffc":
                byteCtor(new byte[] {(byte) 0xFF, (byte) 0xFF, (byte) 0xFF, (byte) 0xFC});
                break;
            case "byte_zero":
                byteCtor(new byte[] {0, 0, 0, 0});
                break;
            case "byte_ffffffff":
                byteCtor(new byte[] {(byte) 0xFF, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF});
                break;
            case "byte_only_print":
                byteCtor(new byte[] {0, 0, 0, 4});
                break;
            case "byte_7fffffff":
                byteCtor(new byte[] {0x7F, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF});
                break;
            case "byte_80000000":
                byteCtor(new byte[] {(byte) 0x80, 0, 0, 0});
                break;
            case "byte_five_extra":
                // Java reads only the first 4 bytes; the trailing 0x09 is ignored.
                byteCtor(new byte[] {0, 0, 0, 4, 9});
                break;
            case "byte_eight":
                // First four bytes are 0 -> 0; trailing 0x04 is ignored.
                byteCtor(new byte[] {0, 0, 0, 0, 0, 0, 0, 4});
                break;
            case "byte_empty":
                byteCtor(new byte[] {});
                break;
            case "byte_one":
                byteCtor(new byte[] {0x04});
                break;
            case "byte_three":
                byteCtor(new byte[] {0, 0, 4});
                break;
            default:
                out.println("UNKNOWN_AP=" + name);
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        String kind = args[0];
        String name = args[1];
        if ("DICT".equals(kind)) {
            runDict(name);
        } else if ("AP".equals(kind)) {
            runAp(name);
        } else {
            out.println("UNKNOWN_KIND=" + kind);
        }
    }
}
