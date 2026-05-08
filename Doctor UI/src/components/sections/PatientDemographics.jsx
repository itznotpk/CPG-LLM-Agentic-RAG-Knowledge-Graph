import React from 'react';
import { User, Calendar, CreditCard, Users } from 'lucide-react';
import { GlassCard } from '../shared';
import { Input, Select } from '../shared';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';

export function PatientDemographics() {
  const { state, dispatch } = useApp();
  const { isDark } = useTheme();
  const { patient } = state;

  const handleChange = (field, value) => {
    dispatch({ type: 'SET_PATIENT', payload: { [field]: value } });
  };

  const genderOptions = [
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
    { value: 'other', label: 'Other' },
  ];

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-[var(--accent-primary)]/20 rounded-xl">
          <User className="w-5 h-5 text-[var(--accent-primary)]" />
        </div>
        <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-800'}`}>Patient Demographics</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          id="patient-name"
          label="Full Name"
          placeholder="Enter patient name"
          value={patient.name}
          onChange={(e) => handleChange('name', e.target.value)}
        />

        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <Input
              id="patient-dob"
              label="Date of Birth"
              type="date"
              value={patient.dob}
              onChange={(e) => handleChange('dob', e.target.value)}
            />
          </div>
          <Input
            id="patient-age"
            label="Age"
            type="number"
            placeholder="Age"
            value={patient.age || ''}
            onChange={(e) => handleChange('age', parseInt(e.target.value))}
          />
        </div>

        <Input
          id="patient-nsn"
          label="National Registration Identity Card (NRIC)"
          placeholder="e.g., 580315-08-1234"
          value={patient.nsn}
          onChange={(e) => handleChange('nsn', e.target.value)}
        />

        <Select
          id="patient-gender"
          label="Gender"
          options={genderOptions}
          placeholder="Select gender"
          value={patient.gender}
          onChange={(e) => handleChange('gender', e.target.value)}
        />
      </div>
    </GlassCard>
  );
}
