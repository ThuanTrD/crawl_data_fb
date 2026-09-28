/**
 * Facebook Lead Intelligence V1 - Phase 6: n8n Code Node for Scoring & Fingerprinting
 */

const crypto = require('crypto');

const INTENT_WEIGHTS = {
  'URGENT_NEED': 50,
  'REQUEST_QUOTE': 45,
  'LOOKING_TO_BUY': 40,
  'LOOKING_FOR_SERVICE': 38,
  'PARTNERSHIP': 25,
  'HIRING': 15,
  'RESEARCH': 10,
  'COMPARISON': 10,
  'RECOMMENDATION': 10,
  'EXISTING_CUSTOMER': 10,
  'DISCUSSION': 5,
  'INFORMATION': 5,
  'IGNORE': 0
};

function computeDedupFingerprint(phone, email, authorId, sourceId) {
  let rawKey = '';
  if (phone && String(phone).trim()) {
    const digits = String(phone).replace(/\D/g, '');
    rawKey = `PHONE:${digits}`;
  } else if (email && String(email).trim()) {
    rawKey = `EMAIL:${String(email).trim().toLowerCase()}`;
  } else if (authorId && String(authorId).trim()) {
    const sId = sourceId ? String(sourceId).trim() : 'UNKNOWN_SOURCE';
    rawKey = `AUTHOR:${String(authorId).trim()}:${sId}`;
  } else {
    rawKey = `ANONYMOUS:${authorId || 'anon'}:${sourceId || 'unknown'}`;
  }
  return crypto.createHash('md5').update(rawKey).digest('hex');
}

function calculateLeadScore(signal) {
  const rulesApplied = [];
  
  // 1. Intent score (0 - 50)
  const intent = signal.intent || 'IGNORE';
  const intentScore = INTENT_WEIGHTS[intent] || 0;
  rulesApplied.push({
    category: 'INTENT',
    rule: `INTENT_${intent}`,
    points: intentScore
  });

  // 2. Contact score (0 - 30)
  let contactScore = 0;
  const phones = signal.extracted_phones || [];
  const emails = signal.extracted_emails || [];
  if (phones.length > 0 && phones[0]) {
    contactScore += 20;
    rulesApplied.push({ category: 'CONTACT', rule: 'HAS_PHONE_NUMBER', points: 20 });
  }
  if (emails.length > 0 && emails[0]) {
    contactScore += 10;
    rulesApplied.push({ category: 'CONTACT', rule: 'HAS_EMAIL_ADDRESS', points: 10 });
  }

  // 3. Profile score (0 - 10)
  let profileScore = 0;
  const meta = signal.signal_metadata || {};
  if (meta.company && String(meta.company).trim()) {
    profileScore += 5;
    rulesApplied.push({ category: 'PROFILE', rule: 'HAS_COMPANY_NAME', points: 5 });
  }
  if (meta.customer_name && String(meta.customer_name).trim()) {
    profileScore += 5;
    rulesApplied.push({ category: 'PROFILE', rule: 'HAS_CUSTOMER_NAME', points: 5 });
  }

  // 4. Context score (0 - 10)
  let contextScore = 0;
  if (meta.quantity && String(meta.quantity).trim()) {
    contextScore += 3;
    rulesApplied.push({ category: 'CONTEXT', rule: 'HAS_SPECIFIC_QUANTITY', points: 3 });
  }
  if (meta.location && String(meta.location).trim()) {
    contextScore += 3;
    rulesApplied.push({ category: 'CONTEXT', rule: 'HAS_PROJECT_LOCATION', points: 3 });
  }
  if (meta.requirement || meta.timeline || meta.budget) {
    contextScore += 4;
    rulesApplied.push({ category: 'CONTEXT', rule: 'HAS_SPECIFIC_REQUIREMENT', points: 4 });
  }

  const totalScore = Math.max(0, Math.min(100, intentScore + contactScore + profileScore + contextScore));
  let tier = 'COLD';
  if (totalScore >= 75) tier = 'HOT';
  else if (totalScore >= 50) tier = 'WARM';

  return {
    intentScore,
    contactScore,
    profileScore,
    contextScore,
    totalScore,
    tier,
    scoringRulesApplied: rulesApplied
  };
}

module.exports = {
  calculateLeadScore,
  computeDedupFingerprint
};
