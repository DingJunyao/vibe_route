from datetime import datetime, timedelta

import pytest

from app.core.security import get_password_hash
from app.models.track import Track, TrackPoint
from app.schemas.track import SplitSegmentRequest
from app.services.road_sign_service import road_sign_service
from app.services.track_service import track_service
from app.services.user_service import user_service
from conftest import _db_env, _track_points


async def _make_track_with_points(db, user):
    track = Track(
        user_id=user.id,
        name='source',
        description='source description',
        original_filename='source.gpx',
        original_crs='wgs84',
        region='id',
        created_by=user.id,
        updated_by=user.id,
        is_valid=True,
    )
    db.add(track)
    await db.flush()
    start = datetime(2026, 9, 1, 8, 0, 0)
    for index in range(5):
        db.add(TrackPoint(
            track_id=track.id,
            point_index=index,
            time=start + timedelta(seconds=index * 10),
            latitude_wgs84=-7.28 - index * 0.001,
            longitude_wgs84=112.73 + index * 0.001,
            latitude_gcj02=-7.29 - index * 0.001,
            longitude_gcj02=112.74 + index * 0.001,
            latitude_bd09=-7.30 - index * 0.001,
            longitude_bd09=112.75 + index * 0.001,
            elevation=10 + index,
            speed=1.5 + index,
            bearing=90 + index,
            province='Bali',
            city='Denpasar',
            district='South',
            province_en='Bali',
            city_en='Denpasar',
            district_en='South',
            road_name='Jalan Uji',
            road_number='3',
            road_name_en='Test Road',
            province_id='Bali',
            city_id='Denpasar',
            district_id='Selatan',
            road_name_id='Jalan Uji',
            region='id',
            memo=f'memo-{index}',
            is_interpolated=(index == 2),
            created_by=user.id,
            updated_by=user.id,
            is_valid=True,
        ))
    await db.commit()
    await db.refresh(track)
    return track


class TestSplitTrack:
    @pytest.mark.asyncio
    async def test_split_preserves_points_and_source(self, workdir):
        async with _db_env(workdir) as (db, user):
            source = await _make_track_with_points(db, user)
            source_before = await _track_points(db, source.id)

            created = await track_service.split_track(
                db,
                user,
                source.id,
                [
                    SplitSegmentRequest(start_index=0, end_index=1),
                    SplitSegmentRequest(start_index=3, end_index=4, name='tail'),
                ],
            )

            assert [track.name for track in created] == ['source (1)', 'tail']
            assert len(await _track_points(db, source.id)) == len(source_before)
            source_after = await _track_points(db, source.id)
            assert [point.id for point in source_after] == [point.id for point in source_before]

            first_points = await _track_points(db, created[0].id)
            assert [point.point_index for point in first_points] == [0, 1]
            assert first_points[0].road_name_id == 'Jalan Uji'
            assert first_points[0].province_id == 'Bali'
            assert first_points[0].memo == 'memo-0'
            assert first_points[0].region == 'id'
            assert first_points[0].interpolation_id is None
            assert first_points[1].is_interpolated is False

            second_points = await _track_points(db, created[1].id)
            assert [point.point_index for point in second_points] == [0, 1]
            assert second_points[0].memo == 'memo-3'
            assert second_points[1].memo == 'memo-4'

    @pytest.mark.asyncio
    async def test_overlapping_segments_are_rejected(self, workdir):
        async with _db_env(workdir) as (db, user):
            source = await _make_track_with_points(db, user)
            with pytest.raises(ValueError):
                await track_service.split_track(
                    db,
                    user,
                    source.id,
                    [
                        SplitSegmentRequest(start_index=0, end_index=2),
                        SplitSegmentRequest(start_index=2, end_index=4),
                    ],
                )


class TestKmlExport:
    @pytest.mark.asyncio
    async def test_path_kml_is_linestring_without_gx_track(self, workdir):
        async with _db_env(workdir) as (db, user):
            source = await _make_track_with_points(db, user)
            filename, content = await track_service.export_points_to_kml(
                db, source.id, user.id, 'wgs84', 'path'
            )
            assert filename.endswith('_path.kml')
            assert '<LineString>' in content
            assert '<coordinates>' in content
            assert '<gx:Track>' not in content
            assert '112.73,-7.28,10' in content

    @pytest.mark.asyncio
    async def test_track_kml_remains_default(self, workdir):
        async with _db_env(workdir) as (db, user):
            source = await _make_track_with_points(db, user)
            _, content = await track_service.export_points_to_kml(
                db, source.id, user.id, 'wgs84'
            )
            assert '<gx:Track>' in content


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_wrong_old_password_and_success(self, workdir):
        async with _db_env(workdir) as (db, user):
            user.hashed_password = get_password_hash('old-hash')
            await db.commit()

            assert not await user_service.change_password(
                db, user, 'wrong-hash', 'new-hash'
            )
            assert await user_service.change_password(
                db, user, 'old-hash', 'new-hash'
            )
            assert await user_service.authenticate(db, user.username, 'new-hash')


def test_road_sign_cache_key_includes_assets():
    first = road_sign_service._generate_cache_key(
        'way', '3', region='id', asset_signature='hmtx-v1:a.ttf:b.ttf'
    )
    second = road_sign_service._generate_cache_key(
        'way', '3', region='id', asset_signature='hmtx-v1:a.ttf:c.ttf'
    )
    assert first != second
