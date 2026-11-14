import { lazy } from 'react';

/** Route-level code splitting: each section is its own chunk. */
export const OverviewPage = lazy(() => import('@/features/overview/OverviewPage'));
export const UniversePage = lazy(() => import('@/features/universe/UniversePage'));
export const AgentsPage = lazy(() => import('@/features/agents/AgentsPage'));
export const CivilizationPage = lazy(() => import('@/features/civilization/CivilizationPage'));
export const RealitiesPage = lazy(() => import('@/features/realities/RealitiesPage'));
export const ObservatoryPage = lazy(() => import('@/features/observatory/ObservatoryPage'));
export const ExperimentsPage = lazy(() => import('@/features/experiments/ExperimentsPage'));
export const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'));
