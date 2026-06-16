package org.apache.pdfbox.filter;

import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;

/**
 * Live oracle probe for the /Filter + /DecodeParms PARSING + PAIRING +
 * chain-resolution surface against Apache PDFBox 3.0.7. Wave 1553, agent C.
 *
 * <p>Declared in package {@code org.apache.pdfbox.filter} so it can call the
 * {@code protected COSDictionary Filter.getDecodeParams(COSDictionary, int)}
 * resolver directly — that method is the gold-standard per-filter parameter
 * extractor every concrete codec invokes inside its {@code decode}. The
 * shared classpath build dir keeps the package compile working.
 *
 * <p>Complements the wave-1529 {@code PdStreamFilterChainFuzzProbe} (which
 * exercises {@code PDStream}'s name/parm-list accessors) and the wave-1543
 * {@code PredictorFilterFuzzProbe} (predictor DECODE math). This probe targets
 * the three resolution primitives that pair a /Filter chain with its
 * /DecodeParms:
 *
 * <pre>
 *   FilterFactory.getFilter(COSName)         -&gt; abbreviation normalization
 *                                               (/Fl -&gt; FlateDecode etc.) +
 *                                               unknown-name IOException
 *   Filter.getDecodeParams(dict, index)      -&gt; per-filter parameter dict
 *                                               (strict name+dict / array+array
 *                                               shape logic, DP-vs-DecodeParms
 *                                               precedence)
 * </pre>
 *
 * <h2>Output</h2> one line per case id, in argv order:
 * <pre>
 *   CASE &lt;id&gt; resolve=&lt;...&gt; parms0=&lt;...&gt; parms1=&lt;...&gt; parms2=&lt;...&gt;
 * </pre>
 *
 * <ul>
 *   <li>{@code resolve} — for each name in the chain (from
 *       {@code COSStream.getFilterList} order), the canonical long name
 *       {@code FilterFactory.getFilter} resolves it to, joined by {@code |};
 *       a name that throws renders as {@code ERR:<Exc>}; a non-resolvable
 *       chain shape (e.g. /Filter is an int) renders {@code SHAPE:<class>}.
 *       Empty chain -&gt; {@code -}.
 *   <li>{@code parmsN} — {@code Filter.getDecodeParams(streamDict, N)}
 *       projected as {@code keys=k:v,k:v} of the returned dict in sorted key
 *       order (integer values only here), or {@code empty} for an empty dict.
 *       {@code ERR:<Exc>} on a throw.
 * </ul>
 */
public final class FilterChainResolveFuzzProbe {

    static final COSName FILTER = COSName.FILTER;
    static final COSName DECODE_PARMS = COSName.DECODE_PARMS;
    static final COSName DP = COSName.DP;

    /** Concrete Filter subclass exposing the protected resolver for the probe. */
    static final class Resolver extends Filter {
        @Override
        public DecodeResult decode(java.io.InputStream a, java.io.OutputStream b,
                COSDictionary c, int d) {
            return new DecodeResult(new COSDictionary());
        }

        @Override
        protected void encode(java.io.InputStream a, java.io.OutputStream b,
                COSDictionary c) {
        }

        COSDictionary resolve(COSDictionary dict, int index) {
            return getDecodeParams(dict, index);
        }
    }

    static final Resolver RESOLVER = new Resolver();

    static COSStream build(String id) {
        COSStream s = new COSStream();
        switch (id) {
            case "single_name_flate":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "single_abbrev_fl":
                s.setItem(FILTER, COSName.getPDFName("Fl"));
                break;
            case "single_abbrev_ahx":
                s.setItem(FILTER, COSName.getPDFName("AHx"));
                break;
            case "single_abbrev_a85":
                s.setItem(FILTER, COSName.getPDFName("A85"));
                break;
            case "single_abbrev_lzw":
                s.setItem(FILTER, COSName.getPDFName("LZW"));
                break;
            case "single_abbrev_rl":
                s.setItem(FILTER, COSName.getPDFName("RL"));
                break;
            case "single_abbrev_ccf":
                s.setItem(FILTER, COSName.getPDFName("CCF"));
                break;
            case "single_abbrev_dct":
                s.setItem(FILTER, COSName.getPDFName("DCT"));
                break;
            case "single_unknown":
                s.setItem(FILTER, COSName.getPDFName("BogusDecode"));
                break;
            case "array_one_flate":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE));
                break;
            case "array_two_a85_flate":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                break;
            case "array_three_abbrev":
                s.setItem(FILTER, arr(COSName.getPDFName("A85"),
                        COSName.getPDFName("Fl"), COSName.getPDFName("AHx")));
                break;
            case "array_with_unknown":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE,
                        COSName.getPDFName("Nope")));
                break;
            case "array_empty":
                s.setItem(FILTER, new COSArray());
                break;
            case "filter_int":
                s.setItem(FILTER, COSInteger.get(7));
                break;
            case "filter_string":
                s.setItem(FILTER, new COSString("FlateDecode"));
                break;
            case "filter_array_with_int":
                COSArray ai = new COSArray();
                ai.add(COSName.FLATE_DECODE);
                ai.add(COSInteger.get(3));
                s.setItem(FILTER, ai);
                break;
            // ---- /DecodeParms pairing ----
            case "name_dict":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, dict("Predictor", 12));
                break;
            case "name_dict_dp_alias":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DP, dict("Predictor", 15));
                break;
            case "name_dict_both_dp_wins":
                // DP and DecodeParms both present, different dicts.
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, dict("Predictor", 2));
                s.setItem(DP, dict("Predictor", 99));
                break;
            case "name_array_parms":
                // single name but array parms -> upstream returns empty.
                s.setItem(FILTER, COSName.FLATE_DECODE);
                COSArray nap = new COSArray();
                nap.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, nap);
                break;
            case "name_int_parms":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, COSInteger.get(3));
                break;
            case "name_name_parms":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, COSName.getPDFName("Oops"));
                break;
            case "array_array_match":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                COSArray aam = new COSArray();
                aam.add(dict("a", 1));
                aam.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, aam);
                break;
            case "array_array_with_null":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                COSArray awn = new COSArray();
                awn.add(COSNull.NULL);
                awn.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, awn);
                break;
            case "array_array_short":
                // 2 filters, 1 parm -> index 1 out of range -> empty.
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                COSArray aas = new COSArray();
                aas.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, aas);
                break;
            case "array_array_long":
                // 1 filter, 2 parms.
                s.setItem(FILTER, arr(COSName.FLATE_DECODE));
                COSArray aal = new COSArray();
                aal.add(dict("Predictor", 12));
                aal.add(dict("Predictor", 2));
                s.setItem(DECODE_PARMS, aal);
                break;
            case "array_array_nondict":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, COSName.FLATE_DECODE));
                COSArray aan = new COSArray();
                aan.add(dict("Predictor", 12));
                aan.add(COSName.getPDFName("Oops"));
                s.setItem(DECODE_PARMS, aan);
                break;
            case "array_single_dict":
                // array filter, single dict parms -> upstream returns empty.
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                s.setItem(DECODE_PARMS, dict("Predictor", 12));
                break;
            case "array_dp_alias":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                COSArray ada = new COSArray();
                ada.add(dict("a", 1));
                ada.add(dict("Predictor", 12));
                s.setItem(DP, ada);
                break;
            case "parms_absent":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                break;
            case "parms_null":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, COSNull.NULL);
                break;
            case "array_array_all_null":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, COSName.FLATE_DECODE));
                COSArray aanull = new COSArray();
                aanull.add(COSNull.NULL);
                aanull.add(COSNull.NULL);
                s.setItem(DECODE_PARMS, aanull);
                break;
            case "no_filter_dict_parms":
                // /DecodeParms present but no /Filter at all.
                s.setItem(DECODE_PARMS, dict("Predictor", 12));
                break;
            default:
                throw new IllegalArgumentException("unknown case " + id);
        }
        return s;
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static COSDictionary dict(String key, int value) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName(key), COSInteger.get(value));
        return d;
    }

    /** Project the resolved (normalized) filter chain. */
    static String resolveProj(COSStream s) {
        COSBase f = s.getDictionaryObject(FILTER);
        if (f == null) {
            return "-";
        }
        java.util.List<COSName> names = new java.util.ArrayList<>();
        if (f instanceof COSName) {
            names.add((COSName) f);
        } else if (f instanceof COSArray) {
            COSArray a = (COSArray) f;
            if (a.size() == 0) {
                return "-";
            }
            for (int i = 0; i < a.size(); i++) {
                COSBase e = a.getObject(i);
                if (e instanceof COSName) {
                    names.add((COSName) e);
                } else {
                    return "SHAPE:" + (e == null ? "null" : e.getClass().getSimpleName());
                }
            }
        } else {
            return "SHAPE:" + f.getClass().getSimpleName();
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < names.size(); i++) {
            if (i > 0) {
                sb.append('|');
            }
            try {
                Filter filter = FilterFactory.INSTANCE.getFilter(names.get(i));
                // The Filter instance has no public name; map by identity to a
                // canonical label via the factory's known long names.
                sb.append(canonicalName(names.get(i)));
            } catch (Exception e) {
                sb.append("ERR:").append(e.getClass().getSimpleName());
            }
        }
        return sb.toString();
    }

    /**
     * Return the long name {@code FilterFactory} maps {@code name} to (so the
     * abbreviation expansion is visible) — derived by re-running the factory
     * lookup against each known long name and comparing identity.
     */
    static String canonicalName(COSName name) {
        Filter want;
        try {
            want = FilterFactory.INSTANCE.getFilter(name);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
        String[] longs = {
            "FlateDecode", "LZWDecode", "ASCII85Decode", "ASCIIHexDecode",
            "RunLengthDecode", "CCITTFaxDecode", "DCTDecode", "JPXDecode",
            "JBIG2Decode", "Crypt", "Identity"
        };
        for (String ln : longs) {
            try {
                if (FilterFactory.INSTANCE.getFilter(COSName.getPDFName(ln)) == want) {
                    return ln;
                }
            } catch (Exception ignore) {
                // not registered under this long name
            }
        }
        return want.getClass().getSimpleName();
    }

    static String parmsProj(COSStream s, int index) {
        COSDictionary d;
        try {
            d = RESOLVER.resolve(s, index);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
        if (d == null || d.size() == 0) {
            return "empty";
        }
        java.util.TreeMap<String, String> sorted = new java.util.TreeMap<>();
        for (COSName k : d.keySet()) {
            COSBase v = d.getDictionaryObject(k);
            String vs;
            if (v instanceof COSInteger) {
                vs = Long.toString(((COSInteger) v).longValue());
            } else {
                vs = v == null ? "null" : v.getClass().getSimpleName();
            }
            sorted.put(k.getName(), vs);
        }
        StringBuilder sb = new StringBuilder("keys=");
        boolean first = true;
        for (java.util.Map.Entry<String, String> e : sorted.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append(e.getKey()).append(':').append(e.getValue());
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        for (String id : args) {
            String resolve;
            String p0;
            String p1;
            String p2;
            try {
                COSStream s = build(id);
                resolve = resolveProj(s);
                p0 = parmsProj(s, 0);
                p1 = parmsProj(s, 1);
                p2 = parmsProj(s, 2);
            } catch (Exception e) {
                resolve = "BUILD:" + e.getClass().getSimpleName();
                p0 = "-";
                p1 = "-";
                p2 = "-";
            }
            out.append("CASE ").append(id)
                    .append(" resolve=").append(resolve)
                    .append(" parms0=").append(p0)
                    .append(" parms1=").append(p1)
                    .append(" parms2=").append(p2)
                    .append('\n');
        }
        System.out.print(out);
    }
}
