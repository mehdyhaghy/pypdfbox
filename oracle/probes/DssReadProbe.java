import java.io.File;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Collection;
import java.util.Set;
import java.util.TreeSet;

import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.SignerInformation;
import org.bouncycastle.cms.SignerInformationStore;
import org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.Store;

/**
 * Live oracle probe: walk a PAdES-LTV PDF's /DSS dictionary and emit the
 * Document Security Store structure facts that PDFBox actually reads back.
 *
 * PDFBox 3.0.7 ships no high-level PDDocumentSecurityStore, so this probe
 * reaches through the COS layer directly:
 *   catalog.getCOSObject().getDictionaryObject("DSS")
 * and reports the document-wide pool sizes, the /VRI key set (the per-
 * signature uppercase-hex SHA-1 of each /Contents octet string), and each
 * VRI entry's /Cert /CRL /OCSP counts. It also re-verifies every signature's
 * detached CMS over the bracketed /ByteRange so a caller can prove the LTV
 * incremental append left the original signed region intact.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> DssReadProbe ltv.pdf
 * Output (stdout, one key=value per line):
 *   dss.present=<true|false>
 *   dss.type=<name-or-NULL>
 *   dss.certs=<count>
 *   dss.crls=<count>
 *   dss.ocsps=<count>
 *   dss.vri.present=<true|false>
 *   dss.vri.keys=<comma-joined sorted hex keys>
 *   vri.<KEY>.cert=<count>
 *   vri.<KEY>.crl=<count>
 *   vri.<KEY>.ocsp=<count>
 *   vri.<KEY>.matchesSig=<true|false>   (KEY == SHA1(/Contents) of some sig)
 *   sig.count=<n>
 *   sig.<i>.vrikey=<uppercase hex SHA-1 of /Contents>
 *   sig.<i>.digestIntact=<true|false>
 *   sig.<i>.byterange=<a,b,c,d>
 */
public final class DssReadProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    /** Count the streams referenced by an indirect-array named field. */
    private static int arrayLen(COSDictionary dict, String key) {
        if (dict == null) {
            return -1;
        }
        COSBase base = dict.getDictionaryObject(COSName.getPDFName(key));
        if (base instanceof COSArray) {
            return ((COSArray) base).size();
        }
        return -1;
    }

    private static String hexUpper(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte x : data) {
            sb.append(Character.forDigit((x >> 4) & 0xF, 16));
            sb.append(Character.forDigit(x & 0xF, 16));
        }
        return sb.toString().toUpperCase(java.util.Locale.ROOT);
    }

    public static void main(String[] args) throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        File file = new File(args[0]);
        byte[] fileBytes = java.nio.file.Files.readAllBytes(file.toPath());

        try (PDDocument doc = Loader.loadPDF(file)) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            COSDictionary catDict = cat.getCOSObject();

            COSBase dssBase = catDict.getDictionaryObject(COSName.getPDFName("DSS"));
            COSDictionary dss = (dssBase instanceof COSDictionary)
                    ? (COSDictionary) dssBase : null;
            out.println("dss.present=" + b(dss != null));

            // Collect the per-signature VRI keys PDFBox derives from /Contents
            // so the probe can flag whether each /VRI key actually matches a
            // signature in the document.
            Set<String> sigVriKeys = new TreeSet<>();
            java.util.List<PDSignature> sigs = doc.getSignatureDictionaries();
            out.println("sig.count=" + sigs.size());
            int si = 0;
            for (PDSignature sig : sigs) {
                String prefix = "sig." + si + ".";
                byte[] contents = sig.getContents();
                String vriKey = "";
                if (contents != null) {
                    MessageDigest sha1 = MessageDigest.getInstance("SHA-1");
                    vriKey = hexUpper(sha1.digest(contents));
                    sigVriKeys.add(vriKey);
                }
                out.println(prefix + "vrikey=" + vriKey);

                int[] br = sig.getByteRange();
                StringBuilder brSb = new StringBuilder();
                if (br != null) {
                    for (int j = 0; j < br.length; j++) {
                        if (j > 0) {
                            brSb.append(',');
                        }
                        brSb.append(br[j]);
                    }
                }
                out.println(prefix + "byterange=" + brSb);

                // Re-verify the detached CMS over the bracketed signed region
                // to prove the LTV incremental append did not disturb it.
                String digestIntact = "false";
                try {
                    byte[] signedContent = sig.getSignedContent(fileBytes);
                    CMSSignedData cms = new CMSSignedData(
                            new CMSProcessableByteArray(signedContent), contents);
                    Store<X509CertificateHolder> certStore = cms.getCertificates();
                    SignerInformationStore signerInfos = cms.getSignerInfos();
                    Collection<SignerInformation> signers = signerInfos.getSigners();
                    for (SignerInformation info : signers) {
                        Collection<X509CertificateHolder> matches =
                                certStore.getMatches(info.getSID());
                        if (matches.isEmpty()) {
                            continue;
                        }
                        X509CertificateHolder certHolder = matches.iterator().next();
                        X509Certificate cert = new JcaX509CertificateConverter()
                                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                .getCertificate(certHolder);
                        boolean ok = info.verify(
                                new JcaSimpleSignerInfoVerifierBuilder()
                                        .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                        .build(certHolder));
                        digestIntact = Boolean.toString(ok);
                        break;
                    }
                } catch (Exception e) {
                    digestIntact = "error:" + e.getClass().getSimpleName();
                }
                out.println(prefix + "digestIntact=" + digestIntact);
                si++;
            }

            if (dss == null) {
                out.println("dss.type=NULL");
                out.println("dss.certs=-1");
                out.println("dss.crls=-1");
                out.println("dss.ocsps=-1");
                out.println("dss.vri.present=false");
                out.println("dss.vri.keys=");
                return;
            }

            COSBase typeBase = dss.getDictionaryObject(COSName.TYPE);
            out.println("dss.type=" + (typeBase instanceof COSName
                    ? ((COSName) typeBase).getName() : "NULL"));

            out.println("dss.certs=" + arrayLen(dss, "Certs"));
            out.println("dss.crls=" + arrayLen(dss, "CRLs"));
            out.println("dss.ocsps=" + arrayLen(dss, "OCSPs"));

            COSBase vriBase = dss.getDictionaryObject(COSName.getPDFName("VRI"));
            COSDictionary vri = (vriBase instanceof COSDictionary)
                    ? (COSDictionary) vriBase : null;
            out.println("dss.vri.present=" + b(vri != null));

            if (vri == null) {
                out.println("dss.vri.keys=");
                return;
            }

            // Sorted key set for a deterministic comparison.
            Set<String> keys = new TreeSet<>();
            for (COSName k : vri.keySet()) {
                keys.add(k.getName());
            }
            out.println("dss.vri.keys=" + String.join(",", keys));

            for (String key : keys) {
                COSBase entryBase = vri.getDictionaryObject(COSName.getPDFName(key));
                COSDictionary entry = (entryBase instanceof COSDictionary)
                        ? (COSDictionary) entryBase : null;
                out.println("vri." + key + ".cert=" + arrayLen(entry, "Cert"));
                out.println("vri." + key + ".crl=" + arrayLen(entry, "CRL"));
                out.println("vri." + key + ".ocsp=" + arrayLen(entry, "OCSP"));
                out.println("vri." + key + ".matchesSig=" + b(sigVriKeys.contains(key)));
            }
        }
    }
}
