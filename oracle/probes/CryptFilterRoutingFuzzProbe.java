import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.encryption.PDCryptFilterDictionary;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;

/**
 * Differential fuzz probe for crypt-filter ROUTING RESOLUTION, Apache PDFBox
 * 3.0.7 (wave 1552, agent C).
 *
 * The existing crypt-filter oracle probes are all file-based round-trips:
 *
 *   - CryptFilterProbe / CryptRoutingProbe — introspect well-formed /StdCF
 *     documents after protect()/save() (routing names + decrypted bytes).
 *   - CryptFilterFuzzProbe / DecryptDataFuzzProbe — decode-dispatch on a corpus
 *     of crafted encrypted PDFs loaded from disk.
 *
 * NONE of them exercise the pure RESOLUTION surface of {@link PDEncryption}:
 * given an /Encrypt dictionary with an arbitrary /CF + /StmF + /StrF + /EFF +
 * /EncryptMetadata shape, what does PDFBox project for
 *
 *   - getStreamFilterName() / getStringFilterName()  (the Identity default when
 *     a slot is absent, PDF 32000-1 §7.6.4.4 Table 20),
 *   - getCryptFilterDictionary(name)  (null when /CF absent or the named filter
 *     is undefined),
 *   - the resolved /CFM of the stream + string default filters,
 *   - getCryptFilterDictionary(name).getCryptFilterMethod() / getLength(),
 *   - isEncryptMetaData()  (the /Encrypt-level flag, default true).
 *
 * This is the surface pypdfbox's StandardSecurityHandler._resolve_cfm /
 * _populate_routing_table relies on. Pinning it both-sides catches divergence
 * in the default-substitution + named-filter-lookup logic without needing a
 * full crypto round-trip.
 *
 * Pure in-memory: builds each /Encrypt COSDictionary shape directly (no parser,
 * no key derivation) and prints one framed line per case. The pypdfbox
 * companion builds the byte-identical PDEncryption and asserts the same fields.
 *
 * Line grammar (one per case, fixed order):
 *   CASE <name> stmF=<resolvedStmFName> strF=<resolvedStrFName>
 *        stmCFM=<cfm|NONEDICT> strCFM=<cfm|NONEDICT> effCFM=<cfm|NONEDICT|NOEFF>
 *        stmLen=<int|NODICT> meta=<true|false>
 *
 * where:
 *   - stmF / strF = enc.getStreamFilterName() / getStringFilterName()
 *     (always non-null: Identity is the default).
 *   - stmCFM = /CFM of getCryptFilterDictionary(getStreamFilterName()), or
 *     NONEDICT when that lookup returns null (Identity slot, or undefined name,
 *     or /CF absent). NOCFM when the dict exists but has no /CFM.
 *   - effCFM mirrors stmCFM but for /EFF (NOEFF when /EFF is absent).
 *   - stmLen = getLength() of the resolved stream crypt-filter dict (bits;
 *     default 40), or NODICT when there is no resolved dict.
 *   - meta = enc.isEncryptMetaData().
 */
public final class CryptFilterRoutingFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // --- 1: V4, /CF/StdCF AESV2, /StmF + /StrF both StdCF, Length 16 ---
        emit(out, "v4_stdcf_aesv2_both",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 2: V4, /CF/StdCF V2 (RC4-128), both StdCF, Length 16 ---
        emit(out, "v4_stdcf_v2_both",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "V2", 16, null))));

        // --- 3: V4, /StmF StdCF but /StrF Identity (mixed routing) ---
        emit(out, "v4_stm_stdcf_str_identity",
                build(4, true, "StdCF", "Identity", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 4: V4, /StmF Identity but /StrF StdCF (mixed, reversed) ---
        emit(out, "v4_stm_identity_str_stdcf",
                build(4, true, "Identity", "StdCF", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 5: V4, /StmF + /StrF both Identity ---
        emit(out, "v4_both_identity",
                build(4, true, "Identity", "Identity", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 6: V4, /StmF absent, /StrF StdCF — absent stm defaults Identity ---
        emit(out, "v4_stm_absent_str_stdcf",
                build(4, true, null, "StdCF", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 7: V4, /StrF absent, /StmF StdCF — absent str defaults Identity ---
        emit(out, "v4_str_absent_stm_stdcf",
                build(4, true, "StdCF", null, null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 8: V4, both /StmF + /StrF absent (with /CF present) ---
        emit(out, "v4_both_absent_cf_present",
                build(4, true, null, null, null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 9: V4, /StmF points at a name NOT in /CF (undefined filter) ---
        emit(out, "v4_stm_undefined_name",
                build(4, true, "MissingCF", "StdCF", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 10: V4, /CF ABSENT entirely while /StmF StdCF (no dict to find) ---
        emit(out, "v4_cf_absent_stm_stdcf",
                build(4, true, "StdCF", "StdCF", null, null));

        // --- 11: V4, custom-named filter (not StdCF) referenced by both ---
        emit(out, "v4_custom_name",
                build(4, true, "MyCF", "MyCF", null,
                        cf(entry("MyCF", "AESV2", 16, null))));

        // --- 12: V4, /CFM None on StdCF ---
        emit(out, "v4_cfm_none",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "None", 16, null))));

        // --- 13: V4, /CFM unknown (Zz) on StdCF ---
        emit(out, "v4_cfm_unknown",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "Zz", 16, null))));

        // --- 14: V4, StdCF entry missing /CFM altogether ---
        emit(out, "v4_no_cfm_key",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", null, 16, null))));

        // --- 15: V4, StdCF entry missing /Length (default 40 bits) ---
        emit(out, "v4_no_length",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "AESV2", -1, null))));

        // --- 16: V4, /Length 5 (legacy bytes-style value left literal) ---
        emit(out, "v4_length_5",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "V2", 5, null))));

        // --- 17: V4, /EFF present pointing at StdCF ---
        emit(out, "v4_eff_stdcf",
                build(4, true, "StdCF", "StdCF", "StdCF",
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 18: V4, /EFF Identity ---
        emit(out, "v4_eff_identity",
                build(4, true, "StdCF", "StdCF", "Identity",
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 19: V4, /EFF undefined name ---
        emit(out, "v4_eff_undefined",
                build(4, true, "StdCF", "StdCF", "NoSuch",
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 20: V4, /EncryptMetadata false ---
        emit(out, "v4_meta_false",
                buildMeta(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "AESV2", 16, null)), false));

        // --- 21: V4, /EncryptMetadata true explicit ---
        emit(out, "v4_meta_true",
                buildMeta(4, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "AESV2", 16, null)), true));

        // --- 22: V5, /CF/StdCF AESV3, both StdCF, Length 32 ---
        emit(out, "v5_stdcf_aesv3_both",
                build(5, true, "StdCF", "StdCF", null,
                        cf(entry("StdCF", "AESV3", 32, null))));

        // --- 23: V5, mixed /StmF AESV3 + /StrF Identity ---
        emit(out, "v5_stm_aesv3_str_identity",
                build(5, true, "StdCF", "Identity", null,
                        cf(entry("StdCF", "AESV3", 32, null))));

        // --- 24: V5, two named filters, StmF -> A, StrF -> B ---
        emit(out, "v5_two_filters",
                build(5, true, "FilterA", "FilterB", null,
                        cf(entry("FilterA", "AESV3", 32, null),
                           entry("FilterB", "AESV3", 32, null))));

        // --- 25: V2 (legacy RC4-128, no /CF at all) ---
        emit(out, "v2_legacy_no_cf",
                buildLegacy(2));

        // --- 26: V1 (legacy RC4-40, no /CF) ---
        emit(out, "v1_legacy_no_cf",
                buildLegacy(1));

        // --- 27: V4, /StmF set to algorithm name directly (V2) no /CF ---
        emit(out, "v4_stmf_is_algo_no_cf",
                build(4, true, "V2", "V2", null, null));

        // --- 28: V4, /CFM AESV2 but referenced via custom default name ---
        emit(out, "v4_default_crypt_filter_name",
                build(4, true, "DefaultCryptFilter", "DefaultCryptFilter", null,
                        cf(entry("DefaultCryptFilter", "AESV2", 16, null))));

        // --- 29: V4, StdCF defined but /StmF Identity + /StrF undefined ---
        emit(out, "v4_stm_identity_str_undefined",
                build(4, true, "Identity", "Ghost", null,
                        cf(entry("StdCF", "AESV2", 16, null))));

        // --- 30: V4, /EncryptMetadata false at /CF level only (not /Encrypt) ---
        emit(out, "v4_cf_level_meta_false",
                build(4, true, "StdCF", "StdCF", null,
                        cf(entryMeta("StdCF", "AESV2", 16, false))));
    }

    // ---- builders -----------------------------------------------------------

    private static COSDictionary entry(String name, String cfm, int len,
            String unused) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("CryptFilter"));
        if (cfm != null) {
            d.setItem(COSName.CFM, COSName.getPDFName(cfm));
        }
        if (len >= 0) {
            d.setItem(COSName.LENGTH, COSInteger.get(len));
        }
        // tag the entry name so cf() can place it
        d.setName(COSName.getPDFName("__entry_name"), name);
        return d;
    }

    private static COSDictionary entryMeta(String name, String cfm, int len,
            boolean meta) {
        COSDictionary d = entry(name, cfm, len, null);
        d.setItem(COSName.getPDFName("EncryptMetadata"),
                COSBoolean.getBoolean(meta));
        return d;
    }

    private static COSDictionary cf(COSDictionary... entries) {
        COSDictionary cf = new COSDictionary();
        for (COSDictionary e : entries) {
            String n = e.getNameAsString("__entry_name");
            e.removeItem(COSName.getPDFName("__entry_name"));
            cf.setItem(COSName.getPDFName(n), e);
        }
        return cf;
    }

    private static PDEncryption build(int v, boolean ignored, String stmF,
            String strF, String eff, COSDictionary cf) {
        return buildMeta(v, ignored, stmF, strF, eff, cf, true);
    }

    private static PDEncryption buildMeta(int v, boolean ignored, String stmF,
            String strF, String eff, COSDictionary cf, boolean explicitMeta) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FILTER, COSName.getPDFName("Standard"));
        d.setInt(COSName.V, v);
        d.setInt(COSName.R, v >= 5 ? 6 : (v == 4 ? 4 : 3));
        d.setInt(COSName.LENGTH, v >= 5 ? 256 : 128);
        if (cf != null) {
            d.setItem(COSName.CF, cf);
        }
        if (stmF != null) {
            d.setItem(COSName.STM_F, COSName.getPDFName(stmF));
        }
        if (strF != null) {
            d.setItem(COSName.STR_F, COSName.getPDFName(strF));
        }
        if (eff != null) {
            d.setItem(COSName.getPDFName("EFF"), COSName.getPDFName(eff));
        }
        d.setItem(COSName.getPDFName("EncryptMetadata"),
                COSBoolean.getBoolean(explicitMeta));
        return new PDEncryption(d);
    }

    private static PDEncryption buildLegacy(int v) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FILTER, COSName.getPDFName("Standard"));
        d.setInt(COSName.V, v);
        d.setInt(COSName.R, v == 1 ? 2 : 3);
        d.setInt(COSName.LENGTH, v == 1 ? 40 : 128);
        return new PDEncryption(d);
    }

    // ---- reporting ----------------------------------------------------------

    private static void emit(PrintStream out, String name, PDEncryption enc) {
        COSName stmFName = enc.getStreamFilterName();
        COSName strFName = enc.getStringFilterName();
        String stmF = stmFName == null ? "Identity" : stmFName.getName();
        String strF = strFName == null ? "Identity" : strFName.getName();
        String stmCFM = resolveCFM(enc, stmF);
        String strCFM = resolveCFM(enc, strF);

        COSBase effBase = enc.getCOSObject().getDictionaryObject(
                COSName.getPDFName("EFF"));
        String effCFM;
        if (effBase == null) {
            effCFM = "NOEFF";
        } else {
            effCFM = resolveCFM(enc, ((COSName) effBase).getName());
        }

        String stmLen = lengthOf(enc, stmF);
        boolean meta = enc.isEncryptMetaData();

        out.println(
                "CASE " + name
                + " stmF=" + stmF
                + " strF=" + strF
                + " stmCFM=" + stmCFM
                + " strCFM=" + strCFM
                + " effCFM=" + effCFM
                + " stmLen=" + stmLen
                + " meta=" + meta);
    }

    private static String resolveCFM(PDEncryption enc, String filterName) {
        if ("Identity".equals(filterName)) {
            return "Identity";
        }
        PDCryptFilterDictionary cfd =
                enc.getCryptFilterDictionary(COSName.getPDFName(filterName));
        if (cfd == null) {
            return "NONEDICT";
        }
        COSName m = cfd.getCryptFilterMethod();
        return m == null ? "NOCFM" : m.getName();
    }

    private static String lengthOf(PDEncryption enc, String filterName) {
        if ("Identity".equals(filterName)) {
            return "NODICT";
        }
        PDCryptFilterDictionary cfd =
                enc.getCryptFilterDictionary(COSName.getPDFName(filterName));
        if (cfd == null) {
            return "NODICT";
        }
        return Integer.toString(cfd.getLength());
    }
}
