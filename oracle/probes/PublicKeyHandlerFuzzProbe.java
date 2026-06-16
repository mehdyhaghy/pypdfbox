import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.PublicKeyProtectionPolicy;
import org.apache.pdfbox.pdmodel.encryption.PublicKeyRecipient;

/**
 * Differential fuzz probe for the PUBLIC-KEY (certificate / Adobe.PubSec)
 * encryption surface of Apache PDFBox 3.0.7 (wave 1550, agent C):
 *
 *   - {@link PublicKeyProtectionPolicy}: empty / single / multi recipient
 *     bookkeeping, getNumberOfRecipients, addRecipient + removeRecipient
 *     (present / absent), iterator ordering, decryption-cert slot, the
 *     inherited key-length / preferAES knobs.
 *   - {@link PublicKeyRecipient}: default (null) construction + the x509 /
 *     permission accessor round-trip.
 *   - {@link AccessPermission#getPermissionBytesForPublicKey()}: the bit
 *     re-encoding (bit 1 ON, bits 7/8 OFF, bits 13..32 cleared) a recipient's
 *     permission undergoes before it is packed into a /Recipients envelope.
 *   - {@link PDEncryption}: the Adobe.PubSec encryption-DICTIONARY shape —
 *     /Filter, /SubFilter variations (adbe.pkcs7.s3/s4/s5), /V + /R combos,
 *     and a MALFORMED /Recipients array (missing / empty / wrong-type entries /
 *     wrong-type value), read back through getRecipients / getRecipientsLength /
 *     getRecipientStringAt.
 *
 * Why no real certificate crypto: driving an actual X.509 cert + RSA key + CMS
 * envelope through the oracle is impractical for a deterministic in-process
 * probe (key generation, BouncyCastle availability, non-reproducible envelope
 * bytes). Per the wave brief we therefore fuzz the POLICY / RECIPIENT /
 * PERMISSION-BIT accessor surface and the encryption-dict SHAPE rather than a
 * full encrypt/decrypt round-trip. PublicKeyRecipient holds a null x509 here;
 * none of the projected fields read the certificate.
 *
 * Each invocation runs ONE named case (arg0 = kind, arg1 = name) and prints a
 * stable {@code key=value} grammar, one per line, UTF-8. The Python sibling
 * mirrors each line and asserts equality, pinning honest divergences in
 * comments.
 *
 * Kinds:
 *   POLICY &lt;name&gt;  — PublicKeyProtectionPolicy / recipient bookkeeping.
 *   PERM   &lt;name&gt;  — getPermissionBytesForPublicKey bit re-encoding.
 *   DICT   &lt;name&gt;  — Adobe.PubSec PDEncryption dictionary shape.
 */
public final class PublicKeyHandlerFuzzProbe {

    static PrintStream out;

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    private static PublicKeyRecipient recip(int perm) {
        PublicKeyRecipient r = new PublicKeyRecipient();
        r.setPermission(new AccessPermission(perm));
        return r;
    }

    // ----------------------------------------------------------------- POLICY

    private static void runPolicy(String name) {
        switch (name) {
            case "empty": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                out.println("count=" + p.getNumberOfRecipients());
                out.println("hasNext=" + b(p.getRecipientsIterator().hasNext()));
                out.println("decryptCertNull=" + b(p.getDecryptionCertificate() == null));
                out.println("keyLength=" + p.getEncryptionKeyLength());
                out.println("preferAES=" + b(p.isPreferAES()));
                break;
            }
            case "single": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                p.addRecipient(recip(-44));
                out.println("count=" + p.getNumberOfRecipients());
                out.println("hasNext=" + b(p.getRecipientsIterator().hasNext()));
                break;
            }
            case "three_order": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                PublicKeyRecipient a = recip(4);
                PublicKeyRecipient b2 = recip(8);
                PublicKeyRecipient c = recip(-1);
                p.addRecipient(a);
                p.addRecipient(b2);
                p.addRecipient(c);
                out.println("count=" + p.getNumberOfRecipients());
                java.util.Iterator<PublicKeyRecipient> it = p.getRecipientsIterator();
                int i = 0;
                while (it.hasNext()) {
                    PublicKeyRecipient r = it.next();
                    out.println("perm" + i + "=" + r.getPermission().getPermissionBytes());
                    i++;
                }
                break;
            }
            case "remove_present": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                PublicKeyRecipient a = recip(4);
                PublicKeyRecipient b2 = recip(8);
                p.addRecipient(a);
                p.addRecipient(b2);
                out.println("removed=" + b(p.removeRecipient(a)));
                out.println("count=" + p.getNumberOfRecipients());
                out.println("firstPerm=" + p.getRecipientsIterator().next()
                        .getPermission().getPermissionBytes());
                break;
            }
            case "remove_absent": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                p.addRecipient(recip(4));
                out.println("removed=" + b(p.removeRecipient(recip(4))));
                out.println("count=" + p.getNumberOfRecipients());
                break;
            }
            case "remove_from_empty": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                out.println("removed=" + b(p.removeRecipient(recip(4))));
                out.println("count=" + p.getNumberOfRecipients());
                break;
            }
            case "key_length_default": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                out.println("keyLength=" + p.getEncryptionKeyLength());
                out.println("preferAES=" + b(p.isPreferAES()));
                break;
            }
            case "key_length_set128": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                p.setEncryptionKeyLength(128);
                p.setPreferAES(true);
                out.println("keyLength=" + p.getEncryptionKeyLength());
                out.println("preferAES=" + b(p.isPreferAES()));
                break;
            }
            case "key_length_set256": {
                PublicKeyProtectionPolicy p = new PublicKeyProtectionPolicy();
                p.setEncryptionKeyLength(256);
                out.println("keyLength=" + p.getEncryptionKeyLength());
                break;
            }
            case "recipient_default_ctor": {
                PublicKeyRecipient r = new PublicKeyRecipient();
                out.println("x509Null=" + b(r.getX509() == null));
                out.println("permNull=" + b(r.getPermission() == null));
                break;
            }
            case "recipient_set_permission": {
                PublicKeyRecipient r = new PublicKeyRecipient();
                AccessPermission ap = new AccessPermission(-44);
                r.setPermission(ap);
                out.println("permNull=" + b(r.getPermission() == null));
                out.println("bytes=" + r.getPermission().getPermissionBytes());
                out.println("same=" + b(r.getPermission() == ap));
                break;
            }
            default:
                out.println("UNKNOWN_POLICY=" + name);
        }
    }

    // ------------------------------------------------------------------- PERM

    private static void emitPerm(int p) {
        AccessPermission ap = new AccessPermission(p);
        out.println("in=" + p);
        out.println("forPublicKey=" + ap.getPermissionBytesForPublicKey());
        // getPermissionBytesForPublicKey mutates in place; re-read confirms.
        out.println("afterBytes=" + ap.getPermissionBytes());
    }

    private static void runPerm(String name) {
        switch (name) {
            case "all_set":
                emitPerm(-1);
                break;
            case "default_minus4":
                emitPerm(-4);
                break;
            case "default_minus44":
                emitPerm(-44);
                break;
            case "all_clear":
                emitPerm(0);
                break;
            case "only_print":
                emitPerm(4);
                break;
            case "only_modify":
                emitPerm(8);
                break;
            case "bit7_8_set":
                // bits 7 (0x40) and 8 (0x80) set -> must be cleared.
                emitPerm(0xC0);
                break;
            case "high_bits_set":
                // bits 13+ set (0x00FFF000) -> must be cleared, bit1 forced on.
                emitPerm(0x00FFF000);
                break;
            case "only_bit1":
                emitPerm(1);
                break;
            case "max_positive":
                emitPerm(Integer.MAX_VALUE);
                break;
            default:
                out.println("UNKNOWN_PERM=" + name);
        }
    }

    // ------------------------------------------------------------------- DICT

    private static COSArray strArray(byte[]... blobs) {
        COSArray a = new COSArray();
        for (byte[] blob : blobs) {
            a.add(new COSString(blob));
        }
        return a;
    }

    private static void emitDict(COSDictionary d) {
        PDEncryption e = new PDEncryption(d);
        out.println("filter=" + e.getFilter());
        out.println("subFilter=" + e.getSubFilter());
        out.println("V=" + e.getVersion());
        out.println("R=" + e.getRevision());
        out.println("Length=" + e.getLength());
        // NOTE: Java PDEncryption has NO getRecipients() accessor (pypdfbox
        // added one). We probe only the upstream surface: getRecipientsLength
        // (throws when /Recipients is missing/non-array) + getRecipientStringAt.
        try {
            out.println("recipientsLen=" + e.getRecipientsLength());
        } catch (Exception ex) {
            out.println("recipientsLen=ERR:" + ex.getClass().getSimpleName());
        }
    }

    private static void runDict(String name) {
        switch (name) {
            case "well_formed_s5_v4": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.SUB_FILTER, COSName.getPDFName("adbe.pkcs7.s5"));
                d.setItem(COSName.V, COSInteger.get(4));
                d.setItem(COSName.R, COSInteger.get(4));
                d.setItem(COSName.LENGTH, COSInteger.get(128));
                d.setItem(COSName.getPDFName("Recipients"),
                        strArray(new byte[] {1, 2, 3}, new byte[] {4, 5}));
                emitDict(d);
                break;
            }
            case "subfilter_s3": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.SUB_FILTER, COSName.getPDFName("adbe.pkcs7.s3"));
                emitDict(d);
                break;
            }
            case "subfilter_s4": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.SUB_FILTER, COSName.getPDFName("adbe.pkcs7.s4"));
                d.setItem(COSName.V, COSInteger.get(2));
                d.setItem(COSName.R, COSInteger.get(3));
                emitDict(d);
                break;
            }
            case "recipients_missing": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.SUB_FILTER, COSName.getPDFName("adbe.pkcs7.s5"));
                emitDict(d);
                break;
            }
            case "recipients_empty": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.getPDFName("Recipients"), new COSArray());
                emitDict(d);
                break;
            }
            case "recipients_wrongtype": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.getPDFName("Recipients"), COSInteger.get(7));
                emitDict(d);
                break;
            }
            case "recipients_bool": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("Recipients"), COSBoolean.TRUE);
                emitDict(d);
                break;
            }
            case "v5_r6_256": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.SUB_FILTER, COSName.getPDFName("adbe.pkcs7.s5"));
                d.setItem(COSName.V, COSInteger.get(5));
                d.setItem(COSName.R, COSInteger.get(6));
                d.setItem(COSName.LENGTH, COSInteger.get(256));
                emitDict(d);
                break;
            }
            case "no_filter": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.SUB_FILTER, COSName.getPDFName("adbe.pkcs7.s5"));
                emitDict(d);
                break;
            }
            case "three_recipients": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PubSec"));
                d.setItem(COSName.getPDFName("Recipients"),
                        strArray(new byte[] {1}, new byte[] {2}, new byte[] {3}));
                PDEncryption e = new PDEncryption(d);
                out.println("recipientsLen=" + e.getRecipientsLength());
                for (int i = 0; i < e.getRecipientsLength(); i++) {
                    COSString s = e.getRecipientStringAt(i);
                    out.println("blob" + i + "=" + s.getBytes().length);
                }
                break;
            }
            default:
                out.println("UNKNOWN_DICT=" + name);
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        String kind = args[0];
        String name = args[1];
        if ("POLICY".equals(kind)) {
            runPolicy(name);
        } else if ("PERM".equals(kind)) {
            runPerm(name);
        } else if ("DICT".equals(kind)) {
            runDict(name);
        } else {
            out.println("UNKNOWN_KIND=" + kind);
        }
    }
}
