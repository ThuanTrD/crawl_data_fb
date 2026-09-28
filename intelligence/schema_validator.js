/**
 * Facebook Lead Intelligence V1 - Phase 5: Schema Validator & Zero-Hallucination Guardrails
 */

const ALLOWED_INTENTS = new Set([
  'IGNORE',
  'INFORMATION',
  'DISCUSSION',
  'RECOMMENDATION',
  'RESEARCH',
  'COMPARISON',
  'LOOKING_TO_BUY',
  'REQUEST_QUOTE',
  'LOOKING_FOR_SERVICE',
  'URGENT_NEED',
  'HIRING',
  'PARTNERSHIP',
  'EXISTING_CUSTOMER'
]);

// Vietnamese Mobile / Landline phone regex
const PHONE_REGEX = /(?:(?:\+84|84|0)[3|5|7|8|9])([0-9]{8})\b/g;

// Standard Email regex
const EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;

// Company indicators in Vietnamese
const COMPANY_INDICATORS = /\b(công ty|cty|tnhh|cổ phần|cp|doanh nghiệp|tập đoàn|nhà thầu|xí nghiệp|đơn vị thi công|tổng thầu)\b/i;

// Self-introduction indicators in Vietnamese
const NAME_INDICATORS = /\b(mình là|em là|tôi là|tên em là|tên mình là|liên hệ mr|mr\.|ms\.|anh |chị |bác )\b/i;

function cleanStringField(val) {
  if (val === null || val === undefined) return null;
  const s = String(val).trim();
  if (s === '' || s.toLowerCase() === 'null' || s.toLowerCase() === 'none' || s.toLowerCase() === 'n/a' || s.toLowerCase() === 'không' || s.toLowerCase() === 'không có') {
    return null;
  }
  return s;
}

/**
 * Validates and enforces zero-hallucination guardrails against source text.
 * @param {object} aiOutput 
 * @param {string} sourceText 
 * @returns {object} { valid: boolean, errors: string[], sanitized: object }
 */
function validateAndSanitizeLead(aiOutput, sourceText) {
  const errors = [];
  if (!aiOutput || typeof aiOutput !== 'object') {
    return {
      valid: false,
      errors: ['AI output must be a non-null object'],
      sanitized: null
    };
  }

  const text = String(sourceText || '').normalize('NFC');
  
  // 1. Boolean flags
  const constructionRelevant = Boolean(aiOutput.construction_relevant);
  const commercialIntent = Boolean(aiOutput.commercial_intent);

  // 2. Intent validation
  let intent = String(aiOutput.intent || '').toUpperCase().trim();
  if (!ALLOWED_INTENTS.has(intent)) {
    if (!constructionRelevant || !commercialIntent) {
      intent = 'IGNORE';
    } else {
      errors.push(`Invalid intent: ${aiOutput.intent}`);
      intent = 'INFORMATION';
    }
  }

  // 3. Clean string fields
  const category = cleanStringField(aiOutput.category);
  const product = cleanStringField(aiOutput.product);
  const quantity = cleanStringField(aiOutput.quantity);
  const requirement = cleanStringField(aiOutput.requirement);
  const location = cleanStringField(aiOutput.location);
  const budget = cleanStringField(aiOutput.budget);
  const timeline = cleanStringField(aiOutput.timeline);

  // 4. Zero-Hallucination Guardrails on Phone
  let phone = null;
  const rawPhones = text.match(PHONE_REGEX);
  if (rawPhones && rawPhones.length > 0) {
    // Canonicalize first phone number: e.g. +84912345678 -> 0912345678
    phone = rawPhones[0].replace(/\s+/g, '').replace(/^\+84/, '0').replace(/^84/, '0');
  }

  // 5. Zero-Hallucination Guardrails on Email
  let email = null;
  const rawEmails = text.match(EMAIL_REGEX);
  if (rawEmails && rawEmails.length > 0) {
    email = rawEmails[0].toLowerCase();
  }

  // 6. Zero-Hallucination Guardrails on Company
  let company = cleanStringField(aiOutput.company);
  if (company) {
    // Only accept company if source text actually contains company indicators or the company name
    const companyLower = company.toLowerCase();
    if (!text.toLowerCase().includes(companyLower) && !COMPANY_INDICATORS.test(text)) {
      company = null; // AI hallucinated company name
    }
  }

  // 7. Zero-Hallucination Guardrails on Customer Name
  let customerName = cleanStringField(aiOutput.customer_name);
  if (customerName) {
    // Only accept if text contains self-introduction or the name appears in text
    const nameLower = customerName.toLowerCase();
    if (!text.toLowerCase().includes(nameLower)) {
      customerName = null; // AI hallucinated name
    }
  }

  // 8. Confidence validation & clamping
  let confidence = Number(aiOutput.confidence);
  if (isNaN(confidence)) {
    confidence = commercialIntent ? 0.8 : 0.2;
  }
  confidence = Math.min(1.0, Math.max(0.0, confidence));

  const sanitized = {
    construction_relevant: constructionRelevant,
    commercial_intent: commercialIntent,
    intent: intent,
    category: category,
    product: product,
    quantity: quantity,
    requirement: requirement,
    location: location,
    budget: budget,
    timeline: timeline,
    customer_name: customerName,
    company: company,
    phone: phone,
    email: email,
    confidence: Number(confidence.toFixed(2))
  };

  return {
    valid: errors.length === 0,
    errors,
    sanitized
  };
}

module.exports = {
  ALLOWED_INTENTS,
  validateAndSanitizeLead
};
